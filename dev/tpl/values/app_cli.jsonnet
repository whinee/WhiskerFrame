{
    "_metadata": {
        "output_path": std.extVar("app_values_output_dir") + "/cli.json"
    },
} + std.parseYaml(importstr "../../values/constants/cli.yaml")