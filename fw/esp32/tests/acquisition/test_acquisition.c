/* Deterministic hardware/RTOS simulation exercising the production C owner. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../components/threads/acquisition_thread.c"

/* Keep assertions concise while production internals use namespaced symbols. */
#define state acquisition_state
#define configured acquisition_configured
#define pending acquisition_pending_frame
#define ready acquisition_data_ready_pending
#define execute acquisition_execute
#define command_queue acquisition_command_queue

#define CHECK(x)                                                                                   \
    do {                                                                                           \
        if (!(x)) {                                                                                \
            printf("FAIL line %d: %s\n", __LINE__, #x);                                            \
            exit(1);                                                                               \
        }                                                                                          \
    } while (0)

static TickType_t ticks, raise_at, disconnect_at;
static bool pin, connected, acquiring, stuck_high, fast_next, invalid_frame;
static unsigned transfers, published, released, errors, live_semaphores;
static uint32_t published_generation;
static void (*during_spi)(void);
static link_t test_link;
static wulpus_pro_session_ref_t test_session = {.link = &test_link, .generation = 7};
static uint8_t frame_data[804];
static wulpus_pro_frame_slot_t frame = {.payload = frame_data, .length = 804};
static bool frame_owned;
static acq_request_t* queued;
static bool run_on_completion;

static void edge(bool high)
{
    if (pin != high) {
        pin = high;
        if (high)
            acquisition_data_ready_isr(NULL);
    }
}

bool board_data_ready(void)
{
    return pin;
}
esp_err_t board_msp_reset(bool asserted)
{
    if (asserted)
        edge(false);
    return ESP_OK;
}
esp_err_t board_data_ready_set_isr(void (*handler)(void*), void* arg)
{
    (void)handler;
    (void)arg;
    return ESP_OK;
}
void wulpus_pro_firmware_info_clear_msp(void)
{
}
void wulpus_pro_firmware_info_set_msp(const uint8_t* response, size_t length)
{
    (void)response;
    CHECK(length == 804);
}
static void transfer(void)
{
    CHECK(pin);
    ++transfers;
    if (during_spi)
        during_spi();
    if (!stuck_high) {
        edge(false);
        if (fast_next)
            edge(true);
    }
}
esp_err_t board_spi_transceive(const void* tx_buffer, void* rx_buffer, size_t length)
{
    CHECK(length == 804);
    CHECK(((const uint8_t*)tx_buffer)[0] == 0xFA);
    memset(rx_buffer, 0, length);
    transfer();
    return ESP_OK;
}
esp_err_t board_spi_transmit(const void* data, size_t length)
{
    CHECK(length == 804);
    CHECK(((const uint8_t*)data)[0] == 0xFA || ((const uint8_t*)data)[0] == 0xFB);
    transfer();
    return ESP_OK;
}
esp_err_t board_spi_receive_dma(void* data, size_t length)
{
    CHECK(length == 804);
    memset(data, 0, length);
    ((uint8_t*)data)[0] = invalid_frame ? 0 : 0xFF;
    transfer();
    return ESP_OK;
}
TickType_t xTaskGetTickCount(void)
{
    return ticks;
}
void vTaskDelay(TickType_t count)
{
    ticks += count;
}
uint32_t ulTaskNotifyTake(BaseType_t clear, TickType_t timeout)
{
    (void)clear;
    CHECK(timeout != portMAX_DELAY);
    ticks += timeout;
    if (raise_at && ticks >= raise_at) {
        raise_at = 0;
        edge(true);
    }
    if (disconnect_at && ticks >= disconnect_at) {
        disconnect_at = 0;
        connected = false;
    }
    return 0;
}
void vTaskNotifyGiveFromISR(TaskHandle_t task, BaseType_t* wake)
{
    (void)task;
    *wake = 0;
}
void xTaskNotifyGive(TaskHandle_t task)
{
    (void)task;
}
BaseType_t xTaskCreate(void (*fn)(void*), const char* name, unsigned stack, void* arg,
                       unsigned priority, TaskHandle_t* task)
{
    (void)fn;
    (void)name;
    (void)stack;
    (void)arg;
    (void)priority;
    *task = (void*)1;
    return pdPASS;
}
QueueHandle_t xQueueCreate(unsigned depth, unsigned size)
{
    (void)depth;
    (void)size;
    return (void*)1;
}
void vQueueDelete(QueueHandle_t q)
{
    (void)q;
}
BaseType_t xQueueSend(QueueHandle_t q, const void* item, TickType_t timeout)
{
    (void)q;
    (void)timeout;
    CHECK(!queued);
    queued = *(acq_request_t* const*)item;
    return pdTRUE;
}
BaseType_t xQueueReceive(QueueHandle_t q, void* item, TickType_t timeout)
{
    (void)q;
    (void)timeout;
    if (!queued)
        return pdFALSE;
    *(acq_request_t**)item = queued;
    queued = NULL;
    return pdTRUE;
}
SemaphoreHandle_t xSemaphoreCreateBinary(void)
{
    ++live_semaphores;
    return calloc(1, sizeof(int));
}
BaseType_t xSemaphoreTake(SemaphoreHandle_t sem, TickType_t timeout)
{
    (void)timeout;
    if (run_on_completion)
        acquisition_process_work();
    return *(int*)sem ? pdTRUE : pdFALSE;
}
BaseType_t xSemaphoreGive(SemaphoreHandle_t sem)
{
    *(int*)sem = 1;
    return pdTRUE;
}
void vSemaphoreDelete(SemaphoreHandle_t sem)
{
    --live_semaphores;
    free(sem);
}
int64_t esp_timer_get_time(void)
{
    return ticks * 1000;
}
bool wulpus_pro_session_is_current(wulpus_pro_session_ref_t s)
{
    return s.link == test_session.link && s.generation == test_session.generation;
}
bool link_is_connected(link_t* link)
{
    return link != NULL && connected;
}
void wulpus_pro_state_set_acquiring(bool value)
{
    acquiring = value;
}
bool wulpus_pro_state_is_acquiring(void)
{
    return acquiring;
}
wulpus_pro_frame_slot_t* wulpus_pro_frame_pool_acquire_for_spi(TickType_t timeout)
{
    (void)timeout;
    if (frame_owned)
        return NULL;
    frame_owned = true;
    return &frame;
}
void wulpus_pro_frame_pool_release(wulpus_pro_frame_slot_t* slot)
{
    CHECK(slot == &frame && frame_owned);
    ++released;
    frame_owned = false;
}
void wulpus_pro_frame_pool_mark_ready(wulpus_pro_frame_slot_t* slot)
{
    CHECK(slot == &frame && frame_owned);
    ++published;
    published_generation = slot->session_generation;
    frame_owned = false;
}
void wulpus_pro_frame_pool_discard_ready(void)
{
}
void packet_tx_notify_frame_ready(void)
{
}
void wulpus_pro_status_set_error(uint32_t flags)
{
    errors |= flags;
}
void wulpus_pro_status_increment_data_ready(void)
{
}
void wulpus_pro_status_increment_spi_complete(void)
{
}
void wulpus_pro_status_increment_spi_error(void)
{
}
void wulpus_pro_status_increment_discarded(void)
{
}
void wulpus_pro_status_increment_overflow(void)
{
}

static esp_err_t command(acq_command_type_t type)
{
    acq_request_t request = {.type = type, .session = test_session, .config = {0xFA}};
    return acquisition_execute(&request);
}
static void fresh(void)
{
    CHECK(!queued && live_semaphores == 0);
    acquisition_pending_frame = NULL;
    frame_owned = false;
    acquisition_state = ACQ_STATE_RESET;
    acquisition_configured = false;
    acquisition_reset_asserted = true;
    acquisition_reset_handshake();
    ticks = raise_at = disconnect_at = 0;
    pin = acquiring = stuck_high = fast_next = invalid_frame = false;
    connected = true;
    test_session.generation = 7;
    transfers = published = released = errors = 0;
    during_spi = NULL;
    run_on_completion = false;
    acquisition_command_queue = (void*)1;
    CHECK(command(ACQ_CMD_BOOT) == ESP_OK);
}
static void configure(void)
{
    edge(true);
    CHECK(command(ACQ_CMD_CONFIGURE) == ESP_OK);
    CHECK(state == ACQ_STATE_CONFIGURED && !pin && transfers == 1);
}
static void disconnect_spi(void)
{
    connected = false;
}

static void queue_stop(void)
{
    acq_request_t* r = calloc(1, sizeof(*r));
    r->type = ACQ_CMD_QUIESCE;
    r->session = test_session;
    r->references = 1;
    r->done = xSemaphoreCreateBinary();
    CHECK(xQueueSend(command_queue, &r, 0) == pdTRUE);
}

int main(void)
{
    fresh();
    configure();
    CHECK(command(ACQ_CMD_ENABLE) == ESP_OK);
    edge(true);
    CHECK(acquisition_process_work());
    CHECK(transfers == 2 && published == 1);
    CHECK(!acquisition_process_work() && transfers == 2);
    puts("PASS fresh boot and one transfer per assertion");

    fresh();
    raise_at = ticks + 1500;
    CHECK(command(ACQ_CMD_CONFIGURE) == ESP_OK && ticks >= 1510);
    puts("PASS delayed MSP startup");

    fresh();
    edge(true);
    fast_next = true;
    CHECK(command(ACQ_CMD_CONFIGURE) == ESP_OK && pin);
    CHECK(acquisition_process_work() && pending != NULL && published == 0);
    CHECK(!acquisition_process_work() && transfers == 2);
    CHECK(command(ACQ_CMD_ENABLE) == ESP_OK && published == 1 && pending == NULL);
    CHECK(published_generation == 7);
    CHECK(acquisition_process_work() && transfers == 3 && published == 2);
    puts("PASS short low pulse, pre-start hold and exactly-once enable");

    fresh();
    configure();
    for (int i = 0; i < 20; ++i) {
        CHECK(command(ACQ_CMD_ENABLE) == ESP_OK);
        edge(true);
        CHECK(acquisition_process_work());
        CHECK(command(ACQ_CMD_QUIESCE) == ESP_OK);
        edge(true);
        CHECK(!acquisition_process_work());
    }
    CHECK(transfers == 21 && published == 20);
    puts("PASS repeated start/stop and quiescent high");

    fresh();
    configure();
    command(ACQ_CMD_ENABLE);
    during_spi = queue_stop;
    edge(true);
    CHECK(acquisition_process_work());
    during_spi = NULL;
    CHECK(!acquisition_process_work() && state == ACQ_STATE_QUIESCENT && !acquiring);
    edge(true);
    CHECK(!acquisition_process_work() && transfers == 2 && live_semaphores == 0);
    puts("PASS stop queued during SPI completes after transfer");

    fresh();
    configure();
    command(ACQ_CMD_QUIESCE);
    raise_at = ticks + 500;
    fast_next = true;
    CHECK(command(ACQ_CMD_RESTART) == ESP_OK && state == ACQ_STATE_WAIT_CONFIG);
    CHECK(transfers == 2 && ready());
    puts("PASS stop at low, delayed next frame and retained restart request");

    fresh();
    configure();
    edge(true);
    acquisition_process_work();
    CHECK(pending != NULL);
    command(ACQ_CMD_QUIESCE);
    CHECK(pending == NULL && released == 1);
    edge(true);
    fast_next = true;
    CHECK(command(ACQ_CMD_RESTART) == ESP_OK && transfers == 3);
    puts("PASS stop with pending frame and high DATA_READY");

    fresh();
    disconnect_at = ticks + 10;
    CHECK(command(ACQ_CMD_CONFIGURE) == ESP_ERR_INVALID_STATE && transfers == 0);
    fresh();
    configure();
    command(ACQ_CMD_ENABLE);
    connected = false;
    edge(true);
    acquisition_process_work();
    CHECK(transfers == 1 && published == 0 && state == ACQ_STATE_QUIESCENT);
    fresh();
    edge(true);
    during_spi = disconnect_spi;
    CHECK(command(ACQ_CMD_CONFIGURE) == ESP_ERR_INVALID_STATE && !configured);
    fresh();
    configure();
    command(ACQ_CMD_ENABLE);
    during_spi = disconnect_spi;
    edge(true);
    acquisition_process_work();
    CHECK(published == 0 && released == 1 && state == ACQ_STATE_QUIESCENT);
    puts("PASS disconnect during configuration and acquisition, including SPI");

    fresh();
    configure();
    command(ACQ_CMD_ENABLE);
    invalid_frame = true;
    edge(true);
    acquisition_process_work();
    CHECK(published == 0 && !configured && state == ACQ_STATE_QUIESCENT && errors);
    CHECK(command(ACQ_CMD_BOOT) == ESP_OK);
    CHECK(!acquisition_process_work());
    edge(true);
    CHECK(command(ACQ_CMD_CONFIGURE) == ESP_OK);
    puts("PASS invalid frame after MSP reset and clean reset recovery");

    fresh();
    edge(true);
    stuck_high = true;
    CHECK(command(ACQ_CMD_CONFIGURE) == ESP_ERR_TIMEOUT && transfers == 1);
    CHECK(!acquisition_process_work() && transfers == 1);
    fresh();
    configure();
    command(ACQ_CMD_QUIESCE);
    edge(true);
    CHECK(command(ACQ_CMD_RESTART) == ESP_ERR_TIMEOUT && transfers == 2);
    puts("PASS no config success without low or restart success without next high");

    fresh();
    uint8_t config[] = {0xFA};
    edge(true);
    CHECK(acquisition_thread_command(ACQ_CMD_CONFIGURE, test_session, config, 1, 5) ==
          ESP_ERR_TIMEOUT);
    CHECK(live_semaphores == 1);
    acquisition_process_work();
    CHECK(transfers == 0 && live_semaphores == 0);
    run_on_completion = true;
    CHECK(acquisition_thread_command(ACQ_CMD_CONFIGURE, test_session, config, 1, 100) == ESP_OK);
    CHECK(transfers == 1 && live_semaphores == 0);
    puts("PASS cancelled queued command, late completion lifetime and independent next result");

    fresh();
    configure();
    edge(true);
    acquisition_process_work();
    ++test_session.generation;
    CHECK(command(ACQ_CMD_ENABLE) == ESP_ERR_INVALID_STATE && published == 0);
    command(ACQ_CMD_QUIESCE);
    CHECK(released == 1);
    puts("PASS old session frame cannot be enabled by new generation");

    fresh();
    configure();
    command(ACQ_CMD_ENABLE);
    acq_request_t stale = {.type = ACQ_CMD_QUIESCE, .session = test_session};
    --stale.session.generation;
    CHECK(execute(&stale) == ESP_ERR_INVALID_STATE && acquiring);
    CHECK(command(ACQ_CMD_DISABLE) == ESP_OK && !acquiring);
    edge(true);
    acquisition_process_work();
    CHECK(pending != NULL && published == 0);
    CHECK(command(ACQ_CMD_ENABLE) == ESP_OK && published == 1);
    puts("PASS stale stop rejected and disable retains one unpublished frame");
    fresh();
    run_on_completion = true;
    uint8_t restart_config[105] = {0xFB};
    uint8_t gui_config[105] = {0xFA};
    for (int cycle = 0; cycle < 3; ++cycle) {
        CHECK(command(ACQ_CMD_QUIESCE) == ESP_OK); /* GUI STOP_RX */
        edge(true);
        fast_next = true;
        unsigned before = transfers;
        CHECK(acquisition_thread_command(ACQ_CMD_CONFIGURE, test_session, restart_config,
                                         sizeof(restart_config), 8000) == ESP_OK);
        CHECK(state == ACQ_STATE_WAIT_CONFIG && !configured && !acquiring);
        CHECK(transfers == before + 1 && ready());
        fast_next = false;
        CHECK(acquisition_thread_command(ACQ_CMD_CONFIGURE, test_session, gui_config,
                                         sizeof(gui_config), 8000) == ESP_OK);
        CHECK(state == ACQ_STATE_CONFIGURED && transfers == before + 2);
        CHECK(command(ACQ_CMD_ENABLE) == ESP_OK);
        edge(true);
        CHECK(acquisition_process_work() && published == (unsigned)cycle + 1);
    }
    puts("PASS GUI STOP_RX -> SET_ACQ_CONFIG(0xFB) -> SET_ACQ_CONFIG(0xFA) -> START_RX");

    fresh();
    run_on_completion = true;
    edge(true);
    CHECK(acquisition_thread_command(ACQ_CMD_CONFIGURE, test_session, restart_config,
                                     sizeof(restart_config), 8000) == ESP_ERR_TIMEOUT);
    CHECK(transfers == 1 && state == ACQ_STATE_QUIESCENT && !configured);
    puts("PASS legacy restart cannot succeed without next configuration-request high");
    return 0;
}
