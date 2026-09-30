import json
import os
import shutil
from pathlib import Path
from typing import Any, Literal

import _jsonnet
import click
from alltheutils.config import read_conf_file, write_to_conf_file
from alltheutils.types import RecursiveDict
from alltheutils.utils import get_value_from_or_update_nested_dict, parent_dir_nth_times
from pydantic import BaseModel
from translate.storage.xliff import xlifffile, xliffunit

DEV_CONF_DIR = os.path.join(parent_dir_nth_times(__file__, 3), "values")
BUILD_CONSTANTS = (
    read_conf_file(os.path.join(DEV_CONF_DIR, "constants", "build.yaml")) or {}
)
CONSTANTS = read_conf_file(os.path.join(DEV_CONF_DIR, "constants", "main.yaml")) or {}

BUILD_TMP_DIR = os.path.abspath(BUILD_CONSTANTS["temporary_dir"])
APP_NAME = CONSTANTS["app_name"]

TRANSLATIONS_BASE_DIR = Path("dev/values/constants/text/")

APP_DIR = os.path.join(parent_dir_nth_times(__file__, 4), APP_NAME)

CONDITIONAL_CONSTANTS = {
    "dev": {
        "python_path": "",
        "script_path": f"{APP_NAME}/backend",
    },
    "build": {
        "python_path": "[PLACEHOLDER]",
        "script_path": "[PLACEHOLDER]",
    },
}

EXTERNAL_VARIABLES = {
    "dev": {
        "app_translations_output_dir": os.path.join(
            APP_DIR,
            "text",
        ),
        "app_values_output_dir": os.path.join(
            APP_DIR,
            "values",
        ),
    },
    "build": {},
}


class EnvironmentValuesGetterContext(BaseModel):
    os: Literal["linux", "win"]  # Operating System


class GetConditionalConstants:
    def __init__(self, env: str) -> None:
        self.env = env

    def dev(self, ctx: EnvironmentValuesGetterContext) -> dict[str, Any]:
        return CONDITIONAL_CONSTANTS[self.env]

    def build(self, ctx: EnvironmentValuesGetterContext) -> dict[str, Any]:
        return CONDITIONAL_CONSTANTS[self.env]

    def get(self, ctx: EnvironmentValuesGetterContext) -> dict[str, Any]:
        return CONDITIONAL_CONSTANTS[self.env]
        return getattr(self, self.env)(ctx)  # type: ignore


class GetExternalVariables:
    def __init__(self, env: str) -> None:
        self.env = env

    def dev(self, ctx: EnvironmentValuesGetterContext) -> dict[str, Any]:
        return EXTERNAL_VARIABLES[self.env]

    def build(self, ctx: EnvironmentValuesGetterContext) -> dict[str, Any]:
        output = EXTERNAL_VARIABLES[self.env]
        os = ctx.os
        if os == "win":
            output["app_values_output_dir"] = rf"{BUILD_TMP_DIR}\values"
        elif os == "linux":
            output["app_values_output_dir"] = f"{BUILD_TMP_DIR}/values"
        return output

    def get(self, ctx: EnvironmentValuesGetterContext) -> dict[str, Any]:
        return getattr(self, self.env)(ctx)  # type: ignore


def get_full_paths_of_files_in_folder(folder_path: str):
    folder = Path(folder_path).resolve()
    return [str(file) for file in folder.glob("**/*") if file.is_file()]


def reset_folder(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    os.makedirs(folder_path, exist_ok=True)


def convert_translation_files(ext_vars_dict: dict[str, Any]):  # noqa: C901
    all_translations = {}

    output_dir = ext_vars_dict["app_translations_output_dir"]

    reset_folder(output_dir)

    for component in TRANSLATIONS_BASE_DIR.iterdir():
        if component.is_dir():
            component_name = component.name
            for xlf_file in component.glob("*.xlf"):
                lang_code = xlf_file.stem  # 'en' from 'en.xlf'

                if lang_code == "_intermediate":
                    continue

                with open(xlf_file, "rb") as f:
                    xliff = xlifffile(f.read())

                result: RecursiveDict = {}

                unit: xliffunit
                for unit in xliff.getunits():
                    get_value_from_or_update_nested_dict(
                        result,
                        unit.getid(),
                        unit.target,
                    )

                get_value_from_or_update_nested_dict(
                    all_translations,
                    f"{lang_code}.{component_name}",
                    result,
                )

    for lang_code, translation in all_translations.items():
        output_file_path = os.path.join(output_dir, f"{lang_code}.json")
        write_to_conf_file(output_file_path, translation)
        click.echo(f"Generated: {os.path.relpath(output_file_path, os.getcwd())}")


@click.group()
@click.option(
    "--env",
    type=click.Choice(["dev", "build"], case_sensitive=True),
    default="dev",
)
@click.option(
    "--os",
    type=click.Choice(["win", "linux"], case_sensitive=True),
    default="linux",
)
@click.pass_context
def cli(ctx, env, os):
    """CLI tool for managing config templates."""
    ctx.obj = {
        "ext_vars": GetExternalVariables(env).get(
            EnvironmentValuesGetterContext(os=os),
        ),
        "conditionals": GetConditionalConstants(env).get(
            EnvironmentValuesGetterContext(os=os),
        ),
    }


@cli.command()
@click.option(
    "--folder_path",
    type=click.Path(exists=True, file_okay=False),
    default="dev/tpl/values",
)
@click.pass_context
def generate(ctx, folder_path):
    """Generate all config templates in a given folder."""
    ext_vars_dict = ctx.obj["ext_vars"]
    output_dir = ext_vars_dict["app_values_output_dir"]

    reset_folder(output_dir)

    for conf_tpl_path in get_full_paths_of_files_in_folder(folder_path):
        json_str = _jsonnet.evaluate_file(conf_tpl_path, ext_vars=ext_vars_dict)
        config = json.loads(json_str)
        metadata = config.pop("_metadata")
        output_path = metadata["output_path"]
        write_to_conf_file(output_path, config)
        click.echo(f"Generated: {os.path.relpath(output_path, os.getcwd())}")

    output_path = os.path.join(
        output_dir,
        "conditionals.json",
    )
    write_to_conf_file(output_path, ctx.obj["conditionals"])
    click.echo(f"Generated: {os.path.relpath(output_path, os.getcwd())}")

    convert_translation_files(ext_vars_dict)


@cli.command()
@click.pass_context
def show_ext_vars(ctx):
    """Display the external variables passed."""
    click.echo(ctx.obj["ext_vars"])


if __name__ == "__main__":
    cli()  # type: ignore
