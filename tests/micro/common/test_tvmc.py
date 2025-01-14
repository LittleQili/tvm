# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import pytest
import subprocess
import shlex
import sys
import logging
import tempfile
import pathlib
import sys
import os

import tvm
from tvm.contrib.download import download_testdata

from ..zephyr.test_utils import ZEPHYR_BOARDS
from ..arduino.test_utils import ARDUINO_BOARDS

TVMC_COMMAND = [sys.executable, "-m", "tvm.driver.tvmc"]

MODEL_URL = "https://github.com/tensorflow/tflite-micro/raw/main/tensorflow/lite/micro/examples/micro_speech/micro_speech.tflite"
MODEL_FILE = "micro_speech.tflite"

# TODO(mehrdadh): replace this with _main from tvm.driver.tvmc.main
# Issue: https://github.com/apache/tvm/issues/9612
def _run_tvmc(cmd_args: list, *args, **kwargs):
    """Run a tvmc command and return the results"""
    cmd_args_list = TVMC_COMMAND + cmd_args
    cwd_str = "" if "cwd" not in kwargs else f" (in cwd: {kwargs['cwd']})"
    logging.debug("run%s: %s", cwd_str, " ".join(shlex.quote(a) for a in cmd_args_list))
    return subprocess.check_call(cmd_args_list, *args, **kwargs)


def _get_target_and_platform(board: str):
    if board in ZEPHYR_BOARDS.keys():
        target_model = ZEPHYR_BOARDS[board]
        platform = "zephyr"
    elif board in ARDUINO_BOARDS.keys():
        target_model = ARDUINO_BOARDS[board]
        platform = "arduino"
    else:
        raise ValueError(f"Board {board} is not supported.")

    target = tvm.target.target.micro(target_model)
    return str(target), platform


@tvm.testing.requires_micro
def test_tvmc_exist(board):
    cmd_result = _run_tvmc(["micro", "-h"])
    assert cmd_result == 0


@tvm.testing.requires_micro
def test_tvmc_model_build_only(board):
    target, platform = _get_target_and_platform(board)

    model_path = model_path = download_testdata(MODEL_URL, MODEL_FILE, module="data")
    temp_dir = pathlib.Path(tempfile.mkdtemp())
    tar_path = str(temp_dir / "model.tar")
    project_dir = str(temp_dir / "project")

    runtime = "crt"
    executor = "graph"

    cmd_result = _run_tvmc(
        [
            "compile",
            model_path,
            f"--target={target}",
            f"--runtime={runtime}",
            f"--runtime-crt-system-lib",
            str(1),
            f"--executor={executor}",
            "--executor-graph-link-params",
            str(0),
            "--output",
            tar_path,
            "--output-format",
            "mlf",
            "--pass-config",
            "tir.disable_vectorize=1",
            "--disabled-pass=AlterOpLayout",
        ]
    )
    assert cmd_result == 0, "tvmc failed in step: compile"

    create_project_cmd = [
        "micro",
        "create-project",
        project_dir,
        tar_path,
        platform,
        "--project-option",
        "project_type=host_driven",
    ]
    if platform == "zephyr":
        create_project_cmd.append(f"{platform}_board={board}")

    cmd_result = _run_tvmc(create_project_cmd)
    assert cmd_result == 0, "tvmc micro failed in step: create-project"

    cmd_result = _run_tvmc(
        ["micro", "build", project_dir, platform, "--project-option", f"{platform}_board={board}"]
    )
    assert cmd_result == 0, "tvmc micro failed in step: build"


@pytest.mark.requires_hardware
@tvm.testing.requires_micro
def test_tvmc_model_run(board):
    target, platform = _get_target_and_platform(board)

    model_path = model_path = download_testdata(MODEL_URL, MODEL_FILE, module="data")
    temp_dir = pathlib.Path(tempfile.mkdtemp())
    tar_path = str(temp_dir / "model.tar")
    project_dir = str(temp_dir / "project")

    runtime = "crt"
    executor = "graph"

    cmd_result = _run_tvmc(
        [
            "compile",
            model_path,
            f"--target={target}",
            f"--runtime={runtime}",
            f"--runtime-crt-system-lib",
            str(1),
            f"--executor={executor}",
            "--executor-graph-link-params",
            str(0),
            "--output",
            tar_path,
            "--output-format",
            "mlf",
            "--pass-config",
            "tir.disable_vectorize=1",
            "--disabled-pass=AlterOpLayout",
        ]
    )
    assert cmd_result == 0, "tvmc failed in step: compile"

    create_project_cmd = [
        "micro",
        "create-project",
        project_dir,
        tar_path,
        platform,
        "--project-option",
        "project_type=host_driven",
    ]
    if platform == "zephyr":
        create_project_cmd.append(f"{platform}_board={board}")

    cmd_result = _run_tvmc(create_project_cmd)
    assert cmd_result == 0, "tvmc micro failed in step: create-project"

    cmd_result = _run_tvmc(
        ["micro", "build", project_dir, platform, "--project-option", f"{platform}_board={board}"]
    )
    assert cmd_result == 0, "tvmc micro failed in step: build"

    cmd_result = _run_tvmc(
        ["micro", "flash", project_dir, platform, "--project-option", f"{platform}_board={board}"]
    )
    assert cmd_result == 0, "tvmc micro failed in step: flash"

    cmd_result = _run_tvmc(
        [
            "run",
            "--device",
            "micro",
            project_dir,
            "--project-option",
            f"{platform}_board={board}",
            "--fill-mode",
            "random",
        ]
    )
    assert cmd_result == 0, "tvmc micro failed in step: run"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__] + sys.argv[1:]))
