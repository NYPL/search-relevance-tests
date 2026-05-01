BASEDIR=$1
APP=$2
COMMIT_ID=$3

SCRIPT_BASE=`pwd`

DESTINATION=$SCRIPT_BASE/applications/$APP/builds/$COMMIT_ID.zip

echo Packaging $BASEDIR to $DESTINATION

cd $BASEDIR
zip -qr $DESTINATION . \
    --exclude '*.git*'

echo Packaged app to $DESTINATION
