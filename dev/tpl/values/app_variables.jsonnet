local dependencies_main = import '../../values/dependencies/main.libsonnet';
local prog_var_main = import '../../values/programmatic_variables/main.dev.json';

{
    "_metadata": {
        "output_path": std.extVar("app_values_output_dir") + "/variables.json"
    }
} + dependencies_main + prog_var_main