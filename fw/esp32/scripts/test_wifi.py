# Copyright (C) 2025 ETH Zurich. All rights reserved.
#
# Author: Cedric Hirschi, ETH Zurich
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# /// script
# dependencies = [
#   "zeroconf",
# ]
# ///
import time

from wulpus import WulpusWiFi, WulpusCommand

esp = WulpusWiFi()

print(esp.get_available())

esp.open()
print(esp.device)

try:
    print(esp.send_command(WulpusCommand.PING))
    print(esp.receive_command())

    print(esp.send_command(WulpusCommand.SET_ACQ_CONFIG, b"0123456789abcdef"))

    # with esp:
    #     print(esp.send_command(WulpusCommand.RESET, receive=False))

    # 
    print("Waiting for data...")
    time.sleep(1)
    while True:
        try:
            print(len(esp.receive_data()[0]))
        except Exception as e:
            print(f"Error receiving data: {e}")
            break

    # print("Resetting device...")
    # print(esp.send_command(WulpusCommand.RESET))
except Exception as e:
    print(f"Error: {e}")
finally:
    esp.close()
    print("Closed connection.")
