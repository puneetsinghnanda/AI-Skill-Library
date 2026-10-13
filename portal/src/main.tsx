import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans/700.css';
import '@fontsource/ibm-plex-mono/500.css';
import './theme/tokens.css';
import './theme/base.css';
import './theme/print.css';

const root = document.getElementById('root');
if (!root) throw new Error('#root is missing');

// `import.meta.env.MODE` is replaced at build time, so a production build drops the demo branch
// entirely; scripts/check-bundle.mjs verifies that (TC-POR-010).
if (import.meta.env.MODE === 'demo') {
  void import('./demo/startDemo').then((m) => m.startDemo(root));
} else {
  void import('./auth/startProd').then((m) => m.startProd(root));
}
