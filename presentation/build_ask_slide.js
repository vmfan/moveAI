const pptxgen = require("pptxgenjs");

// Palette matches presentation/build_deck.js and build_market_slides.js exactly.
const TEAL = "156082";
const NAVY = "0E2841";
const MINT = "E3F5DD";
const WHITE = "FFFFFF";
const GRAY = "8A8A8A";
const AMBER = "B8860B"; // for "unverified / derived / not yet done" flags
const FONT = "Arial";

function newPres() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  return pres;
}

function addPageNum(slide, n) {
  slide.addText(String(n), {
    x: 12.6, y: 7.05, w: 0.5, h: 0.35,
    fontFace: FONT, fontSize: 11, color: GRAY, align: "right", margin: 0,
  });
}

function addTitle(slide, text) {
  slide.addText(text, {
    x: 0.55, y: 0.42, w: 11.5, h: 0.7,
    fontFace: FONT, fontSize: 30, bold: true, color: TEAL, align: "left", margin: 0,
  });
}

function addSubtitle(slide, text) {
  slide.addText(text, {
    x: 0.55, y: 1.08, w: 11.7, h: 0.4,
    fontFace: FONT, fontSize: 13, italic: true, color: NAVY, align: "left", margin: 0,
  });
}

function addSectionLabel(slide, text) {
  slide.addText(text, {
    x: 0.55, y: 0.32, w: 4, h: 0.35,
    fontFace: FONT, fontSize: 12, bold: true, color: GRAY, align: "left", margin: 0,
  });
}

const pres = newPres();

/* ============================================================
   Slide — "Tuning isn't just the model. It's trust."
   Hook: Build 15 ("AI accuracy tuning") is the roadmap's own next
   milestone — reframe it as tuning for two audiences at once: the
   pipeline's error rate, and the customer's willingness to believe it.
   ============================================================ */
{
  const slide = pres.addSlide();
  slide.background = { color: WHITE };
  addSectionLabel(slide, "Ask — 9");
  addTitle(slide, "Tuning Isn't Just the Model. It's Trust.");
  addSubtitle(slide, "Build 15 tunes accuracy. Customer acceptance needs its own tuning loop — or the product gets blacklisted like the industry it's replacing.");

  // Hook strip: the risk, stated in one line, with the tune icon
  slide.addShape("roundRect", {
    x: 0.55, y: 1.65, w: 12.23, h: 0.95,
    rectRadius: 0.1,
    fill: { color: MINT },
    line: { type: "none" },
  });
  slide.addImage({
    path: `${__dirname}/icon_tune.png`,
    x: 0.8, y: 1.85, w: 0.55, h: 0.55,
  });
  slide.addText(
    [
      { text: "\"Automated AI estimation\" is exactly what the Consumer Council's own survey exists to catch. ", options: { bold: true, color: NAVY } },
      { text: "A 3× price spread on an identical job — and a public blacklist culture — is the market MoveAI is entering. Geometric accuracy the customer never sees does not, by itself, earn trust.", options: { color: NAVY } },
    ],
    {
      x: 1.55, y: 1.72, w: 11.0, h: 0.85,
      fontFace: FONT, fontSize: 12.5, align: "left", valign: "middle", margin: 0, lineSpacingMultiple: 1.2,
    }
  );

  // Two significant next steps, as matched cards
  const cards = [
    {
      icon: "icon_verified.png",
      title: "A public accuracy track record",
      body: "Publish quoted-vs-actual variance on real jobs — a running number, not a marketing claim. The same partner data that recalibrates priors.py becomes the trust asset, if we're willing to make it public.",
      ask: "Ask: a calibration partner willing to let us publish results.",
    },
    {
      icon: "icon_gavel.png",
      title: "Independent review, by the body customers already trust",
      body: "The Consumer Council already runs exactly this comparison. Submitting for review — or industry-association audit — turns their existing scrutiny from a threat into a credential.",
      ask: "Ask: an introduction, or a path to inclusion in the next survey.",
    },
  ];

  const cardY = 2.85;
  const cardH = 3.55;
  const gap = 0.35;
  const cardW = (12.23 - gap) / 2;

  cards.forEach((c, i) => {
    const x = 0.55 + i * (cardW + gap);
    slide.addShape("roundRect", {
      x, y: cardY, w: cardW, h: cardH,
      rectRadius: 0.12,
      fill: { color: WHITE },
      line: { color: TEAL, width: 1.25 },
    });
    slide.addImage({
      path: `${__dirname}/${c.icon}`,
      x: x + 0.35, y: cardY + 0.35, w: 0.55, h: 0.55,
    });
    slide.addText(c.title, {
      x: x + 1.05, y: cardY + 0.3, w: cardW - 1.35, h: 0.7,
      fontFace: FONT, fontSize: 16, bold: true, color: TEAL, align: "left", valign: "middle", margin: 0, lineSpacingMultiple: 1.1,
    });
    slide.addText(c.body, {
      x: x + 0.35, y: cardY + 1.15, w: cardW - 0.7, h: 1.55,
      fontFace: FONT, fontSize: 12, color: NAVY, align: "left", margin: 0, lineSpacingMultiple: 1.25,
    });
    slide.addShape("line", {
      x: x + 0.35, y: cardY + 2.75, w: cardW - 0.7, h: 0,
      line: { color: MINT, width: 1.5 },
    });
    slide.addText(c.ask, {
      x: x + 0.35, y: cardY + 2.9, w: cardW - 0.7, h: 0.55,
      fontFace: FONT, fontSize: 11.5, bold: true, color: NAVY, align: "left", margin: 0, lineSpacingMultiple: 1.15,
    });
  });

  slide.addText(
    "Why now: this is the same data as the Build 15 calibration ask (§Calibration, DESIGN.md) — recalibrating priors.py and proving trust externally are one partnership, not two.",
    {
      x: 0.55, y: 6.65, w: 12.2, h: 0.45,
      fontFace: FONT, fontSize: 9.5, italic: true, color: GRAY, align: "left", margin: 0, lineSpacingMultiple: 1.15,
    }
  );
  addPageNum(slide, 5);
}

pres.writeFile({ fileName: `${__dirname}/ask_slide.pptx` }).then(() => {
  console.log("done");
});
