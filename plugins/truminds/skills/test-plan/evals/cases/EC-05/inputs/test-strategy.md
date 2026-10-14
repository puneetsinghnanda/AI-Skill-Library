---
schema: context-section.v1
section: test-strategy
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-support: fbe348e947b1afcfbe1d45c03ee18b4ae491c1b4
---
# Test strategy {#test-strategy}

## Unit tests {#unit-tests}
Jest for api and web. Tests sit in api/test or next to the code as *.test.js files.
Sources: context/generated/test-layout.json#test:sample-support:api/test/tickets.test.js

## End to end {#end-to-end}
Playwright covers the main journeys of the web app.
Sources: sample-support:web/playwright.config.js#L1
