---
profile_version: 1
language: 'java'
build_cmd: 'gradle build -x test'
test_cmd: 'gradle test'
test_one_cmd: 'gradle test --tests {class}'
source_root: 'src/main/java'
test_root: 'src/test/java'
feature_root: 'src/main/java/com/example/game/feature'
generated_paths:
  - 'src/main/java/com/example/game/generated'
lint:
  time_call: 'ServerClock\.now\('
  forbidden_time:
    - 'System\.currentTimeMillis\('
    - 'Instant\.now\('
    - 'LocalDate(Time)?\.now\('
    - 'new Date\(\)'
  random_call: 'GameRandom\.next\w*\('
  forbidden_random:
    - 'new Random\('
    - 'Math\.random\('
    - 'ThreadLocalRandom'
  env_live_check: 'Env\.isLive\(\)'
  metric_call: 'MetricLogger\.userAction\('
  trace_id_call: 'TraceIds\.next\('
  cheat_marker: '@CheatCommand'
  allowed_import: 'com\.example\.game\.feature\.\w+\.api\.'
  blocking_calls:
    - 'Thread\.sleep\('
    - '\.join\(\)'
    - '\.await\('
    - '\.block\(\)'
---

# Fixture profile

Only the frontmatter matters to the linter.
