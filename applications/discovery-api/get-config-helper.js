const fs = require('fs')

const { setCredentials: setKmsCredentials } = require('./lib/kms-helper')
const { loadConfig } = require('./lib/load-config')

let fromIni
// Older versions of the app didn't use this module:
if (fs.existsSync('node_modules/@aws-sdk/credential-providers')) {
  fromIni = require('@aws-sdk/credential-providers').fromIni
}

process.env.ENV = process.env.ENV || 'production'

if (fromIni) {
  setKmsCredentials(fromIni({ profile: 'nypl-digital-dev' }))
}

; (async () => {
  await loadConfig()

  const config = {
    nodes: process.env.ELASTICSEARCH_URI,
    apiKey: process.env.ELASTICSEARCH_API_KEY,
    index: process.env.RESOURCES_INDEX
  }

  const content = JSON.stringify(config)
  fs.writeFileSync(process.argv[2], content)
})()
