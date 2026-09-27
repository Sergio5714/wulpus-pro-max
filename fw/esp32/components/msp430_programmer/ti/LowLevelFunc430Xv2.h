/*
 * ESP32 port interface for TI's SLAU320 FRAM Replicator.
 * The JTAG algorithm remains under the BSD-3-Clause notice in
 * JTAGfunc430FR.c; this adapter is SPDX-License-Identifier: Apache-2.0.
 */
#pragma once
#include <stdint.h>
#include "sdkconfig.h"

typedef uint16_t word;
typedef uint8_t byte;

#define SPYBIWIREJTAG_IF 1
#define SPYBIWIRE_IF 2
#define INTERFACE SPYBIWIREJTAG_IF
#define RAM_START_ADDRESS 0x1c00
#define MAX_ENTRY_TRY 4
#define F_BYTE 8
#define F_WORD 16
#define F_ADDR 20
#define F_LONG 32
#define STATUS_ERROR 0
#define STATUS_OK 1
#define STATUS_FUSEBLOWN 2
#define RSTLOW_SBW 0
#define RSTLOW_JTAG 1
#define RSTHIGH_SBW 2
#define RSTHIGH_JTAG 3
#define SYSBSLPE 0x0002

void msp_ll_set_tms(int);
void msp_ll_set_tdi(int);
void msp_ll_set_tck(int);
void msp_ll_set_test(int);
void msp_ll_set_reset(int);
void msp_ll_set_tclk(int);
void msp_ll_restore_tclk(int);
int msp_ll_get_tdo(void);
void msp_ll_drive(void);
void msp_ll_release(void);
void MsDelay(word);
void usDelay(word);
unsigned long AllShifts(word, unsigned long);
int msp_ll_tdi_level(void);

#define SetTMS() msp_ll_set_tms(1)
#define ClrTMS() msp_ll_set_tms(0)
#define SetTDI() msp_ll_set_tdi(1)
#define ClrTDI() msp_ll_set_tdi(0)
#define SetTCK() msp_ll_set_tck(1)
#define ClrTCK() msp_ll_set_tck(0)
#define SetTST() msp_ll_set_test(1)
#define ClrTST() msp_ll_set_test(0)
#define SetRST() msp_ll_set_reset(1)
#define ClrRST() msp_ll_set_reset(0)
#define SetTCLK() msp_ll_set_tclk(1)
#define ClrTCLK() msp_ll_set_tclk(0)
#define ScanTDO() msp_ll_get_tdo()
#define StoreTCLK() msp_ll_tdi_level()
#define RestoreTCLK(x) msp_ll_restore_tclk((x) != 0)
#define DrvSignals() msp_ll_drive()
#define RlsSignals() msp_ll_release()
#define _DINT() do {} while (0)
#define _EINT() do {} while (0)
