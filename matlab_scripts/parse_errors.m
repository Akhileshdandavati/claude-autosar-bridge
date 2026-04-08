%% parse_errors.m
%% -----------------------------------------------------------------------
%% FOLDER : D:\Auto\claude-autosar-integration\matlab_scripts\
%% FILE   : matlab_scripts\parse_errors.m
%%
%% Called from Python via matlab.engine:
%%   result = eng.parse_errors(error_msg, nargout=1)
%%
%% Classifies a raw MATLAB error string into a structured category.
%% Used by feedback_loop.py to build targeted Claude re-prompts.
%%
%% Args:
%%   error_msg (char) - raw MATLAB error message string
%%
%% Returns:
%%   result (struct) with fields:
%%     .status   = 'OK'
%%     .category = one of the categories below
%%     .details  = original error message
%%
%% Categories:
%%   missing_ref       - unresolved ARXML cross-reference
%%   invalid_type      - data type not in AUTOSAR base types
%%   no_timing_event   - runnable has no associated RTE event
%%   port_conflict     - port direction or interface mismatch
%%   model_error       - generic Simulink model error
%%   unknown           - does not match any known pattern
%% -----------------------------------------------------------------------

function result = parse_errors(error_msg)

    result = struct('status', 'OK', 'category', 'unknown', 'details', error_msg);

    if isempty(error_msg)
        return;
    end

    msg_lower = lower(error_msg);

    %% Missing cross-reference (e.g. unresolved interface or type path)
    if contains(msg_lower, 'not found') || ...
       contains(msg_lower, 'unresolved') || ...
       contains(msg_lower, 'cannot find') || ...
       contains(msg_lower, 'invalid ref')
        result.category = 'missing_ref';
        return;
    end

    %% Invalid data type
    if contains(msg_lower, 'data type') || ...
       contains(msg_lower, 'datatype') || ...
       contains(msg_lower, 'base type') || ...
       contains(msg_lower, 'invalid type')
        result.category = 'invalid_type';
        return;
    end

    %% Missing timing event or runnable mapping
    if contains(msg_lower, 'timing event') || ...
       contains(msg_lower, 'no event') || ...
       contains(msg_lower, 'runnable') || ...
       contains(msg_lower, 'init event')
        result.category = 'no_timing_event';
        return;
    end

    %% Port direction or interface mismatch
    if contains(msg_lower, 'port') || ...
       contains(msg_lower, 'interface') || ...
       contains(msg_lower, 'direction') || ...
       contains(msg_lower, 'provider') || ...
       contains(msg_lower, 'requirer')
        result.category = 'port_conflict';
        return;
    end

    %% Generic Simulink model error
    if contains(msg_lower, 'simulink') || ...
       contains(msg_lower, 'model') || ...
       contains(msg_lower, 'block')
        result.category = 'model_error';
        return;
    end

end
