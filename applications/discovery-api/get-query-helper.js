const fs = require('fs')

const infile = process.argv[2]
const outfile = process.argv[3]
const params = JSON.parse(fs.readFileSync(infile, 'utf8'))

const filters = []
// Add special serial filter for journal_title:
if (params.search_scope === 'journal_title') {
  filters.push({ term: { 'issuance.id': 'urn:biblevel:s' } })
}

// Reassign known search-scope nicknames:
params.search_scope = {
  keyword: 'all',
  journal_title: 'title'
}[params.search_scope] || params.search_scope

// Generate query via buildElasticQuery:
const _priv = {}
require('./lib/resources.js')({}, _priv)
const query = _priv.buildElasticQuery(params)

// Add filters:
if (filters.length) {
  if (!query.bool.filter) query.bool.filter = []
  query.bool.filter = query.bool.filter.concat(filters)
}

// Write query to outfile:
content = JSON.stringify(query, null, 2)
fs.writeFileSync(outfile, content)
