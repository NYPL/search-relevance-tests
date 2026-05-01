ZIP=$1
DESTINATION=$2

echo Un-packaging $ZIP to $DESTINATION

# Remove destination directory - but only if it's a /tmp dir:
if [[ "$DESTINATION" =~ ^/tmp/.* ]] ;
then
  echo Removing $DESTINATION
  rm -rf $DESTINATION
fi

unzip -q $ZIP -d $DESTINATION

# echo "Installed client-kms: in $DESTINATION:"
# ls -l $DESTINATION/node_modules/@aws-sdk

# echo 'All:'
# find $DESTINATION/node_modules/@aws-sdk/client-kms | sed -e "s/[^-][^\/]*\//  |/g" -e "s/|\([^ ]\)/|-\1/"

echo Un-packaged app to $DESTINATION
