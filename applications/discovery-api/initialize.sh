BASEDIR=$1
COMMIT=$2

# Remove destination directory - but only if it's a /tmp dir:
if [[ "$BASEDIR" =~ ^/tmp/.* ]] ;
then
  echo Removing $BASEDIR
  rm -rf $BASEDIR
fi

# Clone repo:
if [ ! -d "$BASEDIR" ]; then
  echo git clone https://github.com/NYPL/discovery-api.git $BASEDIR  # --quiet
  git clone https://github.com/NYPL/discovery-api.git $BASEDIR  # --quiet
fi

cd $BASEDIR

# Checkout commit:
echo git checkout $COMMIT  # --quiet
git checkout $COMMIT --quiet

# echo Open files:
# lsof -i -n -P | wc -l

echo Beginning npm install
# Install dependencies:
# npm install # > /dev/null
# export SET NODE_OPTIONS=--max-old-space-size=40
npm install --logs-dir=. --cache=/tmp/.npm --omit=dev

# echo ..Open files:
# lsof -i -n -P | wc -l

# echo "Installed client-kms: in $BASEDIR:"
# ls -l ./node_modules/@aws-sdk

# echo 'All:'
# find $BASEDIR/node_modules/@aws-sdk/client-kms | sed -e "s/[^-][^\/]*\//  |/g" -e "s/|\([^ ]\)/|-\1/"

# echo "has client?"
# node -e "const resp = require('@aws-sdk/client-kms').KMSClient; console.log(resp)"

echo Done
