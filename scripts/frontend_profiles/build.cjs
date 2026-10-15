/* Synthetic local-only harness: imports the real app modules without backend. */
const path = require('path');
const fs = require('fs');
const root = path.resolve(__dirname, '../..');
const frontend = path.join(root, 'frontend');
const webpack = require(path.join(frontend, 'node_modules/webpack'));
const mode = process.argv[2];
if (!['snapshot', 'window'].includes(mode) || !process.argv[3]) throw new Error('node build.cjs snapshot|window OUTPUT_DIR');
const output = path.resolve(process.argv[3]);
fs.mkdirSync(output, { recursive: true });
const mobile = mode === 'window';
const filename = mobile ? 'mobile.js' : 'bundle.js';
fs.writeFileSync(path.join(output, mobile ? 'mobile.html' : 'index.html'), `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">${mobile ? '<link rel="stylesheet" href="main.css">' : ''}<div id="root"></div><script src="${filename}"></script>`);
if (mobile) {
  const cssDir = path.join(frontend, 'build/static/css');
  const css = fs.readdirSync(cssDir).find(file => /^main\.[a-z0-9]+\.css$/.test(file));
  if (!css) throw new Error('Production main CSS required; build frontend first.');
  fs.copyFileSync(path.join(cssDir, css), path.join(output, 'main.css'));
}
webpack({ mode: 'production', entry: path.join(__dirname, mobile ? 'window-entry.jsx' : 'snapshot-entry.js'), output: { path: output, filename }, optimization: { minimize: false }, resolve: { alias: { '@': path.join(frontend, 'src') }, extensions: ['.js', '.jsx', '.json'], modules: [path.join(frontend, 'node_modules'), 'node_modules'] }, module: { rules: [{ test: /\.jsx?$/, exclude: /node_modules/, use: { loader: path.join(frontend, 'node_modules/babel-loader'), options: { presets: [path.join(frontend, 'node_modules/babel-preset-react-app')] } } }] }, plugins: [new webpack.DefinePlugin({ 'process.env.REACT_APP_BACKEND_URL': JSON.stringify('http://127.0.0.1:8787') })] }, (error, stats) => { if (error || stats.hasErrors()) { process.stderr.write(error?.message || stats.toString({ all: false, errors: true })); process.exitCode = 1; } else process.stdout.write('Synthetic frontend harness ready\n'); });
