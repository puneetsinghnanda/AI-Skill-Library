---
schema: context-section.v1
section: test-strategy
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-orders: 9cfb6b17a90b64aa9aedd2487d3d896a390d119f
---
# Test strategy {#test-strategy}

## Unit tests {#unit-tests}
Jest for api and web. Tests sit in api/test or next to the code as *.test.js files.
Sources: context/generated/test-layout.json#test:sample-orders:api/test/orders.test.js

## End to end {#end-to-end}
Playwright covers the main journeys of the web app.
Sources: sample-orders:web/playwright.config.js#L1
