# Define custom function directory
ARG FUNCTION_DIR="/function"

FROM python:3.12 AS base

# Include global arg in this stage of the build
ARG FUNCTION_DIR

# Copy function code
RUN mkdir -p ${FUNCTION_DIR}
COPY . ${FUNCTION_DIR}

# Install the function's dependencies
RUN pip install \
    --target ${FUNCTION_DIR} \
        awslambdaric
RUN pip install \
    --target ${FUNCTION_DIR} \
        -r ${FUNCTION_DIR}/requirements.txt


# Use a slim version of the base Python image to reduce the final image size
FROM python:3.12-slim AS lambda
# FROM base AS lambda
 
# Give matplotlib a writeable path:
ENV MPLCONFIGDIR=/tmp/.matplotlib

# For discovery-api:
RUN apt update -y && apt install nodejs npm -y

# For un-packaging app versions:
RUN apt install unzip -y

RUN mkdir ~/.ssh
RUN ssh-keyscan -t rsa github.com >> ~/.ssh/known_hosts

# Include global arg in this stage of the build
ARG FUNCTION_DIR
# Set working directory to function root directory
WORKDIR ${FUNCTION_DIR}

# Copy in the built dependencies
COPY --from=base ${FUNCTION_DIR} ${FUNCTION_DIR}

# Set runtime interface client as default command for the container runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
# Pass the name of the function handler as an argument to the runtime
CMD [ "main.lambda_handler" ]


FROM base as local

# For discovery-api:
RUN apt update -y && apt install nodejs npm -y

RUN mkdir ~/.ssh
RUN ssh-keyscan -t rsa github.com >> ~/.ssh/known_hosts

# Include global arg in this stage of the build
ARG FUNCTION_DIR
# Set working directory to function root directory
WORKDIR ${FUNCTION_DIR}

# Copy in the built dependencies
COPY --from=base ${FUNCTION_DIR} ${FUNCTION_DIR}

# ENTRYPOINT ["./run.sh"]
