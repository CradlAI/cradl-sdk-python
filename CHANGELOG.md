# Changelog

## Version 0.7.0 - 2026-11-10

- Agent, model and function versions: `create_*_version` publishes one, `list_*_versions` lists them
- Aliases: `set_*_alias` creates an alias or moves it to a version, and `get_*_alias`, `list_*_aliases` and `delete_*_alias`
- `get_agent`, `get_model`, `get_function`, `create_agent_run` and `get_agent_graph` take qualified ids: `<id>:3`, `<id>:@prod` or `<id>:$latest`
- `update_agent` takes `environments` and `draft_environment_id`, and `set_agent_alias` an `environment_id`; `None` clears either
- `delete_agent(delete_resources=True)` also deletes the agent's hooks, actions, models and validations
- Functions: `list_functions`, `create_function` (uploads the code given as `content`), `get_function` (`get_content=True` for the code), `update_function` and `delete_function`
- `get_agent_graph` and `update_agent_graph`, `list_organizations` and `create_organization`, and `create_hook_run`
- `create_agent_run` takes `trigger_id`, and `list_agent_runs` takes `status`, `sort` and created and updated time ranges
- `list_actions`, `list_hooks`, `list_models`, `list_validations`, `list_functions` and `list_documents` get resources by id: `action_id=[...]` etc.
- `update_hook` takes `function_id`
- Parameters of the API reference by name: `content_type` in `create_document`; `name`, `description` and `retention_in_days` in `update_document`; `name`, `description` and `metadata` in `create_prediction`; `llm_version` and `confidence_version` in `create_model` and `update_model`; `connection_id` in `create_action` and `update_action`; `no_agent_run_update` in `create_action_run`; `status`, `output` and `metadata` in `update_hook_run`; `plan_id`, `url` and `metadata` in `update_organization`; `app_client_id` in `create_user`; `login_urls` and `default_login_url` in `update_app_client`; `order` in `list_logs`
- Ids are quoted in request paths, so an id naming its organization (`cradl:organization:cradl/cradl:function:...`) works
- **Breaking:** `resource_ids` is removed from `create_agent` and `update_agent`, which the API rejects: create resources with `agent_id`
- **Breaking:** the dataset methods (`create_dataset`, `list_datasets`, `get_dataset`, `update_dataset`, `delete_dataset`) are removed: the SDK covers the endpoints of the API reference, which doesn't include datasets. `dataset_id` stays on the document methods
- **Breaking:** Python 3.10 is no longer supported; Python 3.11 to 3.15 are

## Version 0.6.9 - 2026-11-09

- `agent_id` in `create_action`, `create_hook`, `create_model` and `create_validation`: the resource belongs to that agent from the start
- `resource_ids` in `create_agent` and `update_agent` is deprecated, and warns: create the resources with `agent_id` instead
- Update development dependencies (mypy 2.4.1, pytest 9.2.0) and `astral-sh/setup-uv` 10.3.3 in CI

## Version 0.6.8 - 2026-10-26

- Update dependencies to resolve Dependabot security alerts
- Require `requests>=2.33.0` to exclude versions with known vulnerabilities
- Drop tox and `poetry.lock`; use uv and `uv.lock` for development, CI and publishing
- Publish to PyPI with trusted publishing

## Version 0.6.7 - 2026-09-14

- Fix error handling for TooManyRequests and Forbidden errors

## Version 0.6.6 - 2026-04-22

- Get predictions with correct output format in `create_prediction` and `get_prediction`

## Version 0.6.5 - 2026-04-21

- Get predictions if needed from fileserver for `create_prediction` and `get_prediction`

## Version 0.6.4 - 2026-04-20

- Bugfix for backoff in credentials

## Version 0.6.3 - 2026-03-03

- Bugfix for Kinde claims check

## Version 0.6.2 - 2026-02-25

- Add retry when auth endpoint does not provide scopes

## Version 0.6.1 - 2026-02-23

- Add exponential backoff to calls toward the auth endpoint

## Version 0.6.0 - 2026-01-27

- Add update_validation method
- Add get_validation_task method
- Add update_agent_run method
- Add create_hook_run method
- Add update_hook_run method
- Add update_action_run method
- Change input parameter name from validation_task_id to task_id in update_validation_task method

## Version 0.5.0 - 2026-01-16

- Add access_token and access_token_expiration as input arguments to Credentials constructor

## Version 0.4.10 - 2025-11-24

- Add get_agent_statistics method

## Version 0.4.9 - 2025-11-18

- Add delete_agent_run method

## Version 0.4.8 - 2025-11-17

- Add delete_validation method

## Version 0.4.7 - 2025-11-14

- Add create_action_run method

## Version 0.4.6 - 2025-10-17

- Add documentRetentionInDays to update_organization
- Add methods create_role, update_role and delete_role

## Version 0.4.2 - 2025-08-14

- Do not discard documents based on their content type

## Version 0.2.0 - 2025-07-02

- Updated access token generation code to work with new IdP

## Version 0.1.0 - 2025-07-02

- Initial release
