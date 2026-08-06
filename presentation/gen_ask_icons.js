const React = require('react');
const ReactDOMServer = require('react-dom/server');
const sharp = require('sharp');
const path = require('path');
const {
  MdTune, MdChecklistRtl,
} = require('react-icons/md');

const TEAL = '#156082';
const OUT_DIR = __dirname;

const icons = {
  tune: MdTune,             // hook: tuning isn't only a model problem (Ask slide)
  checklist: MdChecklistRtl, // "what we're asking for" list marker (Ask slide)
};

async function run() {
  for (const [name, Icon] of Object.entries(icons)) {
    const svg = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Icon, { color: TEAL, size: 512 })
    );
    const outPath = path.join(OUT_DIR, `icon_${name}.png`);
    await sharp(Buffer.from(svg)).png().toFile(outPath);
    console.log('wrote', outPath);
  }
}
run();
