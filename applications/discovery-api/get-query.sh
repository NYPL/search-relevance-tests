BASEDIR=$1
INFILE=$2
OUTFILE=$3

SCRIPT_BASE=`pwd`

cd $BASEDIR

# Copy helper file over:
cp $SCRIPT_BASE/applications/discovery-api/get-query-helper.js .

# Extract query to OUTFILE:
echo Running: node get-query-helper.js $INFILE $OUTFILE
node get-query-helper.js $INFILE $OUTFILE

rm $BASEDIR/get-query-helper.js
