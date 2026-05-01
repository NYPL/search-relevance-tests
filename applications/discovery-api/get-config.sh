BASEDIR=$1
OUTFILE=$2

SCRIPT_BASE=`pwd`

cd $BASEDIR

# echo "Loading config using client-kms: in $BASEDIR:"
# ls -l ./node_modules/@aws-sdk

# echo "has client?"
# node -e "const resp = require('@aws-sdk/client-kms').KMSClient; console.log(resp)"

# Copy helper file over:
cp $SCRIPT_BASE/applications/discovery-api/get-config-helper.js .

node get-config-helper.js $OUTFILE

rm $BASEDIR/get-config-helper.js
