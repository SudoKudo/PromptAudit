# BigVul cohorts

[BigVul-100](bigvul_100.csv) contains 100 CVEs and 560 C snippets in 280 before/after function pairs. The `cve_id` column gives the selected CVEs. [BigVul-1000](bigvul_1000.csv) contains 1,000 CVEs and 4,296 snippets and includes all 100 sample CVEs.

## Sampling

The source was [`bstee615/bigvul`](https://huggingface.co/datasets/bstee615/bigvul). Cleaning left 2,552 CVEs and 5,772 pairs. The [preparation report](scrub_report.json) records the filters, counts by disclosure year, and sampling seed.

1. Group the cleaned CVEs by disclosure year.
2. Allocate slots in proportion to each year's share of the cleaned CVEs. Round each allocation down and distribute the remaining slots in order of largest fractional remainder.
3. Shuffle CVEs within each year with Python's `random.Random(42)` and select that year's allocation. Keep all cleaned vulnerable/fixed pairs for each selected CVE.

The CSV fixes the membership used for evaluation. Recreating the draw from source requires the original sampling script and ordered cleaned input.

<details>
<summary>CWE distribution by CVE</summary>

The eight BigVul-100 CVEs with blank mappings contribute 70 pairs and are included in the evaluation. The comparison keeps them under **Unassigned CWE**. CWE IDs represented by one or two CVEs in BigVul-1000 are grouped under **Other** in both columns.

| CWE | Description | BigVul-100 CVEs | BigVul-1000 CVEs |
| --- | --- | ---: | ---: |
| CWE-119 | Improper Restriction of Operations within the Bounds of a Memory Buffer | 18 | 182 |
| CWE-20 | Improper Input Validation | 15 | 119 |
| CWE-125 | Out-of-bounds Read | 8 | 86 |
| CWE-399&#42; | Resource Management Errors | 6 | 61 |
| CWE-200 | Exposure of Sensitive Information to an Unauthorized Actor | 4 | 53 |
| CWE-264&#42; | Permissions, Privileges, and Access Controls | 7 | 52 |
| CWE-189&#42; | Numeric Errors | 7 | 49 |
| CWE-416 | Use After Free | 7 | 45 |
| CWE-476 | NULL Pointer Dereference | 1 | 35 |
| CWE-190 | Integer Overflow or Wraparound | 1 | 24 |
| CWE-787 | Out-of-bounds Write | 2 | 20 |
| CWE-362 | Concurrent Execution using Shared Resource with Improper Synchronization | 1 | 17 |
| CWE-772 | Missing Release of Resource after Effective Lifetime | 1 | 13 |
| CWE-310&#42; | Cryptographic Issues | 0 | 11 |
| CWE-284 | Improper Access Control | 0 | 10 |
| CWE-415 | Double Free | 3 | 10 |
| CWE-79 | Improper Neutralization of Input During Web Page Generation | 0 | 7 |
| CWE-17&#42; | DEPRECATED: Code | 0 | 7 |
| CWE-59 | Improper Link Resolution Before File Access | 0 | 6 |
| CWE-254&#42; | 7PK - Security Features | 1 | 6 |
| CWE-369 | Divide By Zero | 1 | 6 |
| CWE-22 | Improper Limitation of a Pathname to a Restricted Directory | 0 | 5 |
| CWE-287 | Improper Authentication | 0 | 5 |
| CWE-19&#42; | Data Processing Errors | 0 | 5 |
| CWE-617 | Reachable Assertion | 0 | 5 |
| CWE-835 | Loop with Unreachable Exit Condition | 2 | 5 |
| CWE-704 | Incorrect Type Conversion or Cast | 0 | 4 |
| CWE-400 | Uncontrolled Resource Consumption | 0 | 3 |
| CWE-770 | Allocation of Resources Without Limits or Throttling | 0 | 3 |
| Other | 36 CWE IDs with one or two CVEs each in BigVul-1000 | 7 | 45 |
| Unassigned CWE | No CWE mapping in the source data | 8 | 101 |
| **Total** | | **100** | **1,000** |

An asterisk marks a MITRE grouping. Names follow the [MITRE CWE List, Version 5.0](https://cwe.mitre.org/data/archive.html), released October 28, 2026. The IDs and mappings come from BigVul.

</details>
