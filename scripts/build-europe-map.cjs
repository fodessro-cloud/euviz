// Builds js/europe-map.json: country outlines of Europe as ready-made SVG paths, so the property
// page draws its map without loading any map library. Geometry: Natural Earth via world-atlas
// (public domain); regions: EU NUTS 2024 from Eurostat GISCO (© EuroGeographics for the
// administrative boundaries). Run by .github/workflows/europe-map.yml (GISCO is reachable there):
// npm i world-atlas@2.0.2 d3-geo@3.1.1 topojson-client@3.1.0, then node scripts/build-europe-map.cjs
const fs = require('fs');
const path = require('path');
const { geoAzimuthalEqualArea, geoPath, geoArea } = require('d3-geo');
const { feature } = require('topojson-client');

const topo = require('world-atlas/countries-50m.json');
const ISO = { // ISO 3166 numeric -> alpha-2, for the countries FINILA has data on
  '040': 'AT', '056': 'BE', '100': 'BG', '191': 'HR', '196': 'CY', '203': 'CZ', '208': 'DK', '233': 'EE',
  '246': 'FI', '250': 'FR', '276': 'DE', '300': 'GR', '348': 'HU', '372': 'IE', '380': 'IT', '428': 'LV',
  '440': 'LT', '442': 'LU', '470': 'MT', '528': 'NL', '616': 'PL', '620': 'PT', '642': 'RO', '703': 'SK',
  '705': 'SI', '724': 'ES', '752': 'SE', '578': 'NO', '352': 'IS', '756': 'CH', '826': 'GB',
};
// NUTS level drawn per country: the level its national statistics publish flat prices for.
// Level 3 where regions are small enough to matter (French departments, Czech and Slovak regions).
const LEVEL3 = new Set(['FR', 'CZ', 'SK', 'PT', 'PL', 'FI', 'NO', 'DK', 'SE', 'SI', 'HR', 'EE', 'LV', 'LT', 'IE', 'BE', 'NL', 'BG', 'RO', 'GR']);
const DATA = new Set(Object.values(ISO));
const NUTS = level => `https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326_LEVL_${level}.geojson`;
// NUTS uses EL for Greece and UK for the United Kingdom.
const NUTS_CC = { EL: 'GR', UK: 'GB' };

const W = 800, H = 700;
const projection = geoAzimuthalEqualArea().rotate([-12, -53]).scale(1050).translate([W / 2 - 40, H / 2 + 20])
  .clipExtent([[0, 0], [W, H]]);
const pathGen = geoPath(projection).digits(1);

(async () => {
  const countries = feature(topo, topo.objects.countries).features
    .map(f => ({ id: ISO[f.id] || '', name: f.properties.name, d: pathGen(f) }))
    .filter(c => c.d && c.d.length > 8);
  const regions = [];
  for (const level of [2, 3]) {
    const geo = await (await fetch(NUTS(level))).json();
    for (const f of geo.features) {
      const p = f.properties;
      const c = NUTS_CC[p.CNTR_CODE] || p.CNTR_CODE;
      if (!DATA.has(c) || LEVEL3.has(c) !== (level === 3)) continue;
      const d = pathGen({ type: 'Feature', geometry: rewind(f.geometry) });
      if (d && d.length > 8) regions.push({ id: p.NUTS_ID, c, name: p.NAME_LATN || p.NUTS_NAME, d });
    }
  }
  const out = { w: W, h: H, source: 'Natural Earth via world-atlas; regions © EuroGeographics (Eurostat GISCO, NUTS 2024)', countries, regions };
  fs.writeFileSync(path.join(__dirname, '..', 'js', 'europe-map.json'), JSON.stringify(out));
  console.log(`${countries.length} shapes, ${countries.filter(c => c.id).length} with data, ${regions.length} regions, ${(JSON.stringify(out).length / 1024).toFixed(0)} KB`);
})();

// d3-geo reads rings in the opposite winding from standard GeoJSON: a polygon that comes out
// bigger than half the globe was read inside out, so flip each such polygon.
function rewind(g) {
  const fix = poly => geoArea({ type: 'Polygon', coordinates: poly }) > 2 * Math.PI ? poly.map(r => r.slice().reverse()) : poly;
  if (g.type === 'Polygon') return { type: 'Polygon', coordinates: fix(g.coordinates) };
  if (g.type === 'MultiPolygon') return { type: 'MultiPolygon', coordinates: g.coordinates.map(fix) };
  return g;
}
