---
schema: context-section.v1
section: test-strategy
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-library: 86f214bb00d63dc2770f522e9dcd4db333555a21
---
# Test strategy {#test-strategy}

## Unit tests {#unit-tests}
Jest for api and web. Tests sit in api/test or next to the code as *.test.js files.
Sources: context/generated/test-layout.json#test:sample-library:api/test/loans.test.js

## End to end {#end-to-end}
Playwright covers the main journeys of the web app.
Sources: sample-library:web/playwright.config.js#L1
