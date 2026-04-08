%% run_simulation.m
%% -----------------------------------------------------------------------
%% FOLDER : D:\Auto\claude-autosar-integration\matlab_scripts\
%% FILE   : matlab_scripts\run_simulation.m
%%
%% Called from Python via matlab.engine:
%%   result = eng.run_simulation(model_name, nargout=1)
%%
%% Runs a Simulink simulation on an already-loaded model.
%% The model must have been imported with import_autosar_arxml.m first.
%%
%% Args:
%%   model_name (char) - name of the loaded Simulink model
%%
%% Returns:
%%   result (struct) with fields:
%%     .status  = 'OK' or 'ERROR'
%%     .message = error message (on failure)
%% -----------------------------------------------------------------------

function result = run_simulation(model_name)

    result = struct('status', 'ERROR', 'message', '');

    try
        %% Check the model is loaded
        if ~bdIsLoaded(model_name)
            result.message = sprintf('Model %s is not loaded.', model_name);
            return;
        end

        %% Configure simulation parameters
        in = Simulink.SimulationInput(model_name);
        in = in.setModelParameter('StopTime',     '0.1');
        in = in.setModelParameter('Solver',       'ode3');
        in = in.setModelParameter('FixedStep',    '0.001');
        in = in.setModelParameter('SimulationMode', 'normal');

        %% Run simulation
        sim(in);

        result.status = 'OK';

    catch ME
        result.status  = 'ERROR';
        result.message = ME.message;
    end

end
