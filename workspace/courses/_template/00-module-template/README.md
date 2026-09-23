# Module Template

Copy and rename this directory for each module in a course. Update
`module.yaml`, add private source materials locally, then run the mnemo
pipeline (`mnemo ingest` → `mnemo draft` → author → `mnemo audit` →
`mnemo import`) against them.

Draft into a `.mnemo.yaml` manifest and provide the destination deck name with
`--deck`. Choose `--directions term-to-definition` (default),
`definition-to-term`, or `both`. Mnemo intentionally has no CSV input or
export workflow.
