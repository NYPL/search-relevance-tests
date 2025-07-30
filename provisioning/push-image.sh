ACCOUNT=946183545209
REGION=us-east-1
REPO=search-relevance-tests
REGISTRY=${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com
IMAGE_ID=$(git rev-parse HEAD)

# Get environment (qa/production). Default qa
ENVIRONMENT="${1:-qa}"

aws ecr get-login-password \
    --region ${REGION} \
| docker login \
    --username AWS \
    --password-stdin ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com

docker buildx build --platform linux/amd64 -t ${REGISTRY}/${REPO}:${IMAGE_ID} --target lambda .
docker push ${REGISTRY}/${REPO}:${IMAGE_ID}
docker tag ${REGISTRY}/${REPO}:${IMAGE_ID} ${REGISTRY}/${REPO}:${ENVIRONMENT}
docker push ${REGISTRY}/${REPO}:${ENVIRONMENT}

