"""
Copyright (C) 2026 Sergei Vostrikov

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0


Compile and run the production acquisition owner against deterministic mocks.
"""

import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "acquisition-tests"
OUT.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
compiler = env.get("CC") or shutil.which("cl" if os.name == "nt" else "cc")
if compiler is None and os.name == "nt":
    programs = Path(os.environ["ProgramFiles(x86)"])
    versions = sorted((programs / "Microsoft Visual Studio").glob("*/*/VC/Tools/MSVC/*"))
    sdks = sorted((programs / "Windows Kits/10/Include").glob("10.*"))
    if versions and sdks:
        vc, sdk = versions[-1], sdks[-1]
        compiler = str(vc / "bin/Hostx64/x64/cl.exe")
        env["PATH"] = str(Path(compiler).parent) + os.pathsep + env["PATH"]
        env["INCLUDE"] = os.pathsep.join(map(str, [vc / "include", sdk / "ucrt", sdk / "shared", sdk / "um"]))
        lib = sdk.parents[1] / "Lib" / sdk.name
        env["LIB"] = os.pathsep.join(map(str, [vc / "lib/x64", lib / "ucrt/x64", lib / "um/x64"]))
if compiler is None:
    raise SystemExit("Set CC to a native C11 compiler (or run in a Visual Studio developer shell).")
includes = ["tests/acquisition/stubs", "components/control/include", "components/frames/include",
            "components/links/include", "components/threads"]
for name in ("test_acquisition", "test_usb_connection"):
    source = f"tests/acquisition/{name}.c"
    exe = OUT / (name + (".exe" if os.name == "nt" else ""))
    if Path(compiler).name.lower() in ("cl", "cl.exe"):
        sources = ([source, "components/threads/acquisition_handshake.c",
                    "components/threads/acquisition_frames.c"]
                   if name == "test_acquisition" else [source])
        args = [compiler, "/nologo", "/std:c11", "/W3", "/WX", *["/I" + p for p in includes], *sources,
                "/Fo" + str(OUT) + "\\", "/Fe" + str(exe)]
    else:
        sources = ([source, "components/threads/acquisition_handshake.c",
                    "components/threads/acquisition_frames.c"]
                   if name == "test_acquisition" else [source])
        args = [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", *["-I" + p for p in includes], *sources, "-o", str(exe)]
    subprocess.run(args, cwd=ROOT, env=env, check=True)
    subprocess.run([str(exe)], cwd=ROOT, env=env, check=True)
