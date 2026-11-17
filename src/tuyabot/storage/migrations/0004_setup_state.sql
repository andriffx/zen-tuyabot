-- 0004_setup_state.sql — setup completion lives in app_state (runtime flag),
-- not in app_settings (user-editable configuration). Remove the duplicate.

DELETE FROM app_settings WHERE key = 'system.setup_complete';
