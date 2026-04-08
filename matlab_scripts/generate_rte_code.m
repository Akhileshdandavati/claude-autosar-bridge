%% generate_rte_code.m
%% -----------------------------------------------------------------------
%% FOLDER : D:\Auto\claude-autosar-integration\matlab_scripts\
%% FILE   : matlab_scripts\generate_rte_code.m
%%
%% Called from Python via matlab.engine:
%%   result = eng.generate_rte_code(model_name, output_dir, nargout=1)
%%
%% Triggers AUTOSAR C code generation using MATLAB's AUTOSAR Blockset.
%% Produces: Rte_Types.h, Rte_<swc>.h, <swc>.c, <swc>.h
%% Copies generated files to output_dir.
%%
%% Args:
%%   model_name (char) - name of the loaded Simulink model
%%   output_dir (char) - absolute path to copy generated files into
%%
%% Returns:
%%   result (struct) with fields:
%%     .status  = 'OK' or 'ERROR'
%%     .message = error message or list of generated files (on success)
%% -----------------------------------------------------------------------

function result = generate_rte_code(model_name, output_dir)

    result = struct('status', 'ERROR', 'message', '');

    try
        %% Check model is loaded
        if ~bdIsLoaded(model_name)
            result.message = sprintf('Model %s is not loaded.', model_name);
            return;
        end

        %% Set AUTOSAR code generation target
        set_param(model_name, 'SystemTargetFile', 'autosar.tlc');
        set_param(model_name, 'GenerateReport',   'off');
        set_param(model_name, 'LaunchReport',     'off');

        %% Build (triggers code generation)
        slbuild(model_name);

        %% Copy generated files to output_dir
        gen_dir = fullfile(pwd, 'slprj', 'autosar', model_name);
        if exist(gen_dir, 'dir')
            if ~exist(output_dir, 'dir')
                mkdir(output_dir);
            end
            copyfile(gen_dir, output_dir);
            result.message = ['Generated files copied to ' output_dir];
        else
            result.message = ['Code generated but slprj dir not found: ' gen_dir];
        end

        result.status = 'OK';

    catch ME
        result.status  = 'ERROR';
        result.message = ME.message;
    end

end
