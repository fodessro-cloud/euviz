// Builds js/europe-map.json: country outlines of Europe as ready-made SVG paths, so the property
// page draws its map without loading any map library. Geometry: Natural Earth via world-atlas
// (public domain). Run once: npm i world-atlas@2.0.2 d3-geo@3.1.1 topojson-client@3.1.0, then
// node scripts/build-europe-map.cjs
const fs = require('fs');
const path = require('path');
const { geoAzimuthalEqualArea, geoPath } = require('d3-geo');
const { feature } = require('topojson-client');

const topo = require('world-atlas/countries-50m.json');
const ISO = { // ISO 3166 numeric -> alpha-2, for the countries FINILA has data on
  '040': 'AT', '056': 'BE', '100': 'BG', '191': 'HR', '196': 'CY', '203': 'CZ', '208': 'DK', '233': 'EE',
  '246': 'FI', '250': 'FR', '276': 'DE', '300': 'GR', '348': 'HU', '372': 'IE', '380': 'IT', '428': 'LV',
  '440': 'LT', '442': 'LU', '470': 'MT', '528': 'NL', '616': 'PL', '620': 'PT', '642': 'RO', '703': 'SK',
  '705': 'SI', '724': 'ES', '752': 'SE', '578': 'NO', '352': 'IS', '756': 'CH', '826': 'GB',
};
const W = 800, H = 700;
const projection = geoAzimuthalEqualArea().rotate([-12, -53]).scale(1050).translate([W / 2 - 40, H / 2 + 20])
  .clipExtent([[0, 0], [W, H]]);
const pathGen = geoPath(projection).digits(1);
const countries = feature(topo, topo.objects.countries).features
  .map(f => ({ id: ISO[f.id] || '', name: f.properties.name, d: pathGen(f) }))
  .filter(c => c.d && c.d.length > 8);
const out = { w: W, h: H, source: 'Natural Earth via world-atlas', countries };
fs.writeFileSync(path.join(__dirname, '..', 'js', 'europe-map.json'), JSON.stringify(out));
console.log(`${countries.length} shapes, ${countries.filter(c => c.id).length} with data, ${(JSON.stringify(out).length / 1024).toFixed(0)} KB`);
