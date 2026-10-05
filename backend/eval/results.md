# Evaluation results

Run: 2026-10-05 09:23 UTC  
Answer model: `openai/gpt-oss-120b`  
Router model: `openai/gpt-oss-20b`

## Summary

| Type | Passed |
|---|---|
| digest | 6/6 |
| fact | 3/6 |
| follow_up | 2/2 |
| search | 2/2 |
| general | 1/1 |
| out_of_scope | 3/3 |
| **all** | **17/20** |

## Questions

| Id | Result | Intent | Cited | Seconds | Problems |
|---|---|---|---|---|---|
| digest-knights | pass | digest | gr-213948 | 10.6 | - |
| digest-mmda | pass | digest | gr-171947 | 8.5 | - |
| digest-pearl-dean | pass | digest | gr-148222 | 8.1 | - |
| digest-ang | pass | digest | gr-182835 | 20.3 | - |
| digest-disini | pass | digest | gr-203335 | 35.1 | - |
| digest-oposa | pass | digest | gr-101083 | 27.6 | - |
| fact-knights-why-dismissed | pass | follow_up | gr-213948 | 18.4 | - |
| fact-mmda-water-standard | FAIL | follow_up | gr-171947 | 13.7 | missing one of ['swimming', 'contact recreation', 'skin-diving'] |
| fact-pearl-dean-copyright-scope | pass | follow_up | gr-148222 | 8.0 | - |
| fact-ang-ree-criminal | pass | follow_up | gr-182835 | 13.4 | - |
| fact-disini-struck-down | FAIL | follow_up | gr-203335 | 27.1 | missing one of ['section 12', 'sec. 12']; missing one of ['section 19', 'sec. 19'] |
| fact-oposa-doctrine | FAIL | follow_up | gr-101083 | 16.0 | missing one of ['intergenerational']; missing one of ['healthful ecology', 'balanced and healthful'] |
| followup-oposa-petitioners | pass | follow_up | gr-101083 | 11.5 | - |
| followup-knights-ponente | pass | follow_up | gr-213948 | 21.8 | - |
| search-environment | pass | search | gr-101083, gr-171947 | 13.2 | - |
| search-cyber | pass | search | gr-203335 | 12.1 | - |
| general-mandamus | pass | general | - | 1.6 | - |
| oos-eat-bulaga | pass | out_of_scope | - | 10.8 | - |
| oos-admin-circular | pass | out_of_scope | - | 23.4 | - |
| oos-click-wrap | pass | out_of_scope | - | 10.9 | - |
