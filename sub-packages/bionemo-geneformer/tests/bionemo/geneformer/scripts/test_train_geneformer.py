# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-Apache2
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

import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict

import pytest
from lightning.fabric.plugins.environments.lightning import find_free_network_port

from bionemo.core.data.load import load
from bionemo.geneformer.scripts.train_geneformer import get_parser, main
from bionemo.llm.model.biobert.transformer_specs import BiobertSpecOption
from bionemo.llm.utils.datamodule_utils import parse_kwargs_to_arglist
from bionemo.testing import megatron_parallel_state_utils


@pytest.fixture
def data_path() -> Path:
    """Gets the path to the directory with cellx small dataset in Single Cell Memmap format.
    Returns:
        A Path object that is the directory with the specified test data.
    """
    return load("single_cell/testdata-20241203") / "cellxgene_2023-12-15_small_processed_scdl"


def test_bionemo2_rootdir(data_path):
    assert data_path.exists(), "Could not find test data directory."
    assert data_path.is_dir(), "Test data directory is supposed to be a directory."


@pytest.mark.parametrize("create_checkpoint_callback", [True, False])
def test_main_runs(tmpdir, create_checkpoint_callback: bool, data_path: Path):
    result_dir = Path(tmpdir.mkdir("results"))

    with megatron_parallel_state_utils.distributed_model_parallel_state():
        main(
            data_dir=data_path,
            num_nodes=1,
            devices=1,
            seq_length=128,
            result_dir=result_dir,
            wandb_project=None,
            wandb_offline=True,
            num_steps=5,
            limit_val_batches=1,
            val_check_interval=2,
            num_dataset_workers=0,
            biobert_spec_option=BiobertSpecOption.bert_layer_local_spec,
            lr=1e-4,
            micro_batch_size=2,
            accumulate_grad_batches=2,
            cosine_rampup_frac=0.01,
            cosine_hold_frac=0.01,
            precision="bf16-mixed",
            experiment_name="test_experiment",
            resume_if_exists=False,
            create_tensorboard_logger=False,
            num_layers=2,
            num_attention_heads=2,
            hidden_size=4,
            ffn_hidden_size=4 * 2,
            create_checkpoint_callback=create_checkpoint_callback,
        )

    assert (result_dir / "test_experiment").exists(), "Could not find test experiment directory."
    assert (result_dir / "test_experiment").is_dir(), "Test experiment directory is supposed to be a directory."
    children = list((result_dir / "test_experiment").iterdir())
    assert len(children) == 1, f"Expected 1 child in test experiment directory, found {children}."
    uq_rundir = children[0]  # it will be some date.

    expected_exists = create_checkpoint_callback
    actual_exists = (result_dir / "test_experiment" / uq_rundir / "checkpoints").exists()

    assert expected_exists == actual_exists, (
        f"Checkpoints directory existence mismatch. "
        f"Expected: {'exists' if expected_exists else 'does not exist'}, "
        f"Found: {'exists' if actual_exists else 'does not exist'}."
    )

    if create_checkpoint_callback:
        assert (result_dir / "test_experiment" / uq_rundir / "checkpoints").is_dir(), (
            "Test experiment checkpoints directory is supposed to be a directory."
        )
    assert (result_dir / "test_experiment" / uq_rundir / "nemo_log_globalrank-0_localrank-0.txt").is_file(), (
        "Could not find experiment log."
    )


@pytest.mark.parametrize("limit_val_batches", [0.0, 1])
def test_val_dataloader_in_main_runs_with_limit_val_batches(tmpdir, data_path, limit_val_batches: float):
    result_dir = Path(tmpdir.mkdir("results"))
    with megatron_parallel_state_utils.distributed_model_parallel_state():
        main(
            data_dir=data_path,
            num_nodes=1,
            devices=1,
            seq_length=128,
            result_dir=result_dir,
            wandb_project=None,
            wandb_offline=True,
            num_steps=5,
            limit_val_batches=limit_val_batches,
            val_check_interval=2,
            num_dataset_workers=0,
            biobert_spec_option=BiobertSpecOption.bert_layer_local_spec,
            lr=1e-4,
            micro_batch_size=2,
            accumulate_grad_batches=2,
            cosine_rampup_frac=0.01,
            cosine_hold_frac=0.01,
            precision="bf16-mixed",
            experiment_name="test_experiment",
            resume_if_exists=False,
            create_tensorboard_logger=False,
            num_layers=2,
            num_attention_heads=2,
            hidden_size=4,
            ffn_hidden_size=4 * 2,
        )

    assert (result_dir / "test_experiment").exists(), "Could not find test experiment directory."
    assert (result_dir / "test_experiment").is_dir(), "Test experiment directory is supposed to be a directory."
    children = list((result_dir / "test_experiment").iterdir())
    assert len(children) == 1, f"Expected 1 child in test experiment directory, found {children}."
    uq_rundir = children[0]  # it will be some date.
    assert (result_dir / "test_experiment" / uq_rundir / "checkpoints").exists(), (
        "Could not find test experiment checkpoints directory."
    )
    assert (result_dir / "test_experiment" / uq_rundir / "checkpoints").is_dir(), (
        "Test experiment checkpoints directory is supposed to be a directory."
    )
    assert (result_dir / "test_experiment" / uq_rundir / "nemo_log_globalrank-0_localrank-0.txt").is_file(), (
        "Could not find experiment log."
    )


def test_throws_tok_not_in_vocab_error(tmpdir, data_path):
    result_dir = Path(tmpdir.mkdir("results"))
    with pytest.raises(ValueError) as error_info:
        with megatron_parallel_state_utils.distributed_model_parallel_state():
            main(
                data_dir=data_path,
                num_nodes=1,
                devices=1,
                seq_length=128,
                result_dir=result_dir,
                wandb_project=None,
                wandb_offline=True,
                num_steps=55,
                limit_val_batches=1,
                val_check_interval=1,
                num_dataset_workers=0,
                biobert_spec_option=BiobertSpecOption.bert_layer_local_spec,
                lr=1e-4,
                micro_batch_size=2,
                accumulate_grad_batches=2,
                cosine_rampup_frac=0.01,
                cosine_hold_frac=0.01,
                precision="bf16-mixed",
                experiment_name="test_experiment",
                resume_if_exists=False,
                create_tensorboard_logger=False,
                include_unrecognized_vocab_in_dataset=True,
            )

    assert "not in the tokenizer vocab." in str(error_info.value)


@pytest.mark.slow  # TODO: https://jirasw.nvidia.com/browse/BIONEMO-677, figure out why this is so slow.
def test_pretrain_cli(tmpdir, data_path):
    result_dir = Path(tmpdir.mkdir("results"))
    open_port = find_free_network_port()
    # NOTE: if you need to change the following command, please update the README.md example.
    cmd_str = f"""train_geneformer     \
    --data-dir {data_path}     \
    --result-dir {result_dir}     \
    --experiment-name test_experiment     \
    --num-gpus 1  \
    --num-nodes 1 \
    --val-check-interval 2 \
    --num-dataset-workers 0 \
    --num-steps 5 \
    --seq-length 128 \
    --limit-val-batches 2 \
    --micro-batch-size 2 \
    --accumulate-grad-batches 2 \
    --num-layers 2 \
    --num-attention-heads 2 \
    --hidden-size 4 \
    --ffn-hidden-size 8
    """.strip()
    env = dict(**os.environ)  # a local copy of the environment
    env["MASTER_PORT"] = str(open_port)
    cmd = shlex.split(cmd_str)
    result = subprocess.run(
        cmd,
        cwd=tmpdir,
        env=env,
        capture_output=True,
    )
    assert result.returncode == 0, f"Pretrain script failed: {cmd_str}"
    assert (result_dir / "test_experiment").exists(), "Could not find test experiment directory."


@pytest.fixture(scope="function")
def required_args_reference() -> Dict[str, str]:
    """
    This fixture provides a dictionary of required arguments for the pretraining script.

    It includes the following keys:
    - data_dir: The path to the data directory.

    Returns:
        A dictionary with the required arguments for the pretraining script.
    """
    return {
        "data_dir": "path/to/cellxgene_2023-12-15_small",
    }


def test_required_data_dir(required_args_reference):
    """
    Test data_dir is required.

    Args:
        required_args_reference (Dict[str, str]): A dictionary with the required arguments for the pretraining script.
    """
    required_args_reference.pop("data_dir")
    arglist = parse_kwargs_to_arglist(required_args_reference)
    parser = get_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(arglist)


#### test expected behavior on parser ####
@pytest.mark.parametrize("limit_val_batches", [0.1, 0.5, 1.0])
def test_limit_val_batches_is_float(required_args_reference, limit_val_batches):
    """
    Test whether limit_val_batches can be parsed as a float.

    Args:
        required_args_reference (Dict[str, str]): A dictionary with the required arguments for the pretraining script.
        limit_val_batches (float): The value of limit_val_batches.
    """
    required_args_reference["limit_val_batches"] = limit_val_batches
    arglist = parse_kwargs_to_arglist(required_args_reference)
    parser = get_parser()
    parser.parse_args(arglist)


@pytest.mark.parametrize("limit_val_batches", ["0.1", "0.5", "1.0"])
def test_limit_val_batches_is_float_string(required_args_reference, limit_val_batches):
    """
    Test whether limit_val_batches can be parsed as a string of float.

    Args:
        required_args_reference (Dict[str, str]): A dictionary with the required arguments for the pretraining script.
        limit_val_batches (float): The value of limit_val_batches.
    """
    required_args_reference["limit_val_batches"] = limit_val_batches
    arglist = parse_kwargs_to_arglist(required_args_reference)
    parser = get_parser()
    parser.parse_args(arglist)


@pytest.mark.parametrize("limit_val_batches", [None, "None"])
def test_limit_val_batches_is_none(required_args_reference, limit_val_batches):
    """
    Test whether limit_val_batches can be parsed as none.

    Args:
        required_args_reference (Dict[str, str]): A dictionary with the required arguments for the pretraining script.
    """
    required_args_reference["limit_val_batches"] = limit_val_batches
    arglist = parse_kwargs_to_arglist(required_args_reference)
    parser = get_parser()
    args = parser.parse_args(arglist)
    assert args.limit_val_batches is None


@pytest.mark.parametrize("limit_val_batches", [1, 2])
def test_limit_val_batches_is_int(required_args_reference, limit_val_batches):
    """
    Test whether limit_val_batches can be parsed as integer.

    Args:
        required_args_reference (Dict[str, str]): A dictionary with the required arguments for the pretraining script.
        limit_val_batches (int): The value of limit_val_batches.
    """
    required_args_reference["limit_val_batches"] = limit_val_batches
    arglist = parse_kwargs_to_arglist(required_args_reference)
    parser = get_parser()
    parser.parse_args(arglist)
