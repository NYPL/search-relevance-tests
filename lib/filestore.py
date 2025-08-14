import botocore
import boto3
import io
import os
import mimetypes

from nypl_py_utils.functions.log_helper import create_log


logger = create_log("S3")


def write_to_s3(key, data, public=False):
    bucket = S3BucketWrapper("research-catalog-stats")
    acl = "public-read" if public else "private"
    bucket.put(key, data, acl=acl)


def get_from_s3(remote_path, local_path):
    bucket = S3BucketWrapper("research-catalog-stats")
    bucket.get(remote_path, local_path)


def upload_dir(source_path, prefix, public=False, exclude=[]):
    logger.info(f"Uploading {source_path} to {prefix}")
    bucket = S3BucketWrapper("research-catalog-stats")
    acl = "public-read" if public else "private"
    bucket.upload_dir_s3(source_path, prefix, acl=acl, exclude=exclude)


def download_dir(prefix, local_path):
    logger.info(f"Downloading {prefix} to {local_path}")
    bucket = S3BucketWrapper("research-catalog-stats")
    bucket.download_dir(prefix, local_path)


class S3BucketWrapper:
    """Encapsulates S3 object actions."""

    def __init__(self, bucket_name):
        """
        :param bucket_name:
        """

        self.client = boto3.client("s3")
        self.resource = boto3.resource("s3")
        self.bucket_name = bucket_name

    def get(self, key, local_path):
        s3_object = self.resource.Object(self.bucket_name, key)

        data = io.BytesIO()
        s3_object.download_fileobj(data)

        with open(local_path, "wb") as f:
            f.write(data.getbuffer())

    def put(self, key, data, acl="public-read"):
        """
        Upload data to the object.

        :param data: The data to upload. This can either be bytes or a string. When this
                     argument is a string, it is interpreted as a file name, which is
                     opened in read bytes mode.
        """

        s3_object = self.resource.Object(self.bucket_name, key)

        put_data = data
        if isinstance(data, str):
            try:
                put_data = open(data, "rb")
            except IOError:
                logger.error(f"Expected file name or binary data, got '{data}'.")
                raise

        try:
            s3_object.put(Body=put_data, ACL=acl, ContentType="text/html")
            s3_object.wait_until_exists()
        except botocore.exceptions.ClientError:
            logger.error(
                f"Couldn't put object '{s3_object.key} to bucket {s3_object.bucket_name}"
            )
            raise
        finally:
            if getattr(put_data, "close", None):
                put_data.close()

    def download_dir(self, prefix, local_path, start_prefix=None):
        if start_prefix is None:
            start_prefix = prefix

        paginator = self.client.get_paginator("list_objects")
        for result in paginator.paginate(
            Bucket=self.bucket_name, Delimiter="/", Prefix=prefix
        ):
            if result.get("CommonPrefixes") is not None:
                for subdir in result.get("CommonPrefixes"):
                    self.download_dir(subdir.get("Prefix"), local_path, start_prefix)
            if result.get("Contents") is not None:
                for file in result.get("Contents"):
                    key_relative = file.get("Key").replace(start_prefix, "")
                    if not os.path.exists(
                        os.path.dirname(local_path + os.sep + key_relative)
                    ):
                        os.makedirs(os.path.dirname(local_path + os.sep + key_relative))
                    full_local_path = local_path + os.sep + key_relative
                    s3_path = file.get("Key")
                    self.resource.meta.client.download_file(
                        self.bucket_name, s3_path, full_local_path
                    )

    def upload_dir_s3(self, source_dir, dst_prefix="", acl="private", exclude=[]):
        # enumerate local files recursively
        for root, dirs, files in os.walk(source_dir):

            for filename in files:
                # construct the full local path
                local_path = os.path.join(root, filename)

                # construct the full Dropbox path
                relative_path = os.path.relpath(local_path, source_dir)
                s3_path = os.path.join(dst_prefix, relative_path)

                file_mime_type, _ = mimetypes.guess_type(local_path)
                try:
                    extra = {"ACL": acl, "ContentType": file_mime_type}
                    if file_mime_type is None:
                        logger.warn(
                            f"Skipping uploading {local_path} because unrecognized content-type"
                        )
                    elif filename in exclude:
                        logger.debug(f"  Skipping uploading {filename}")
                    else:
                        self.client.upload_file(
                            local_path, self.bucket_name, s3_path, ExtraArgs=extra
                        )

                    # try:
                    #    client.delete_object(Bucket=bucket, Key=s3_path)
                    # except:
                    #    print "Unable to delete %s..." % s3_path
                except Exception as e:
                    logger.error(f"Failed to upload {local_path} to {s3_path}: {e}")

        self.remove_stale_directories(dst_prefix, source_dir)

    def remove_stale_directories(self, prefix, local_path, start_prefix=None):
        if start_prefix is None:
            start_prefix = prefix

        paginator = self.client.get_paginator("list_objects")
        for result in paginator.paginate(
            Bucket=self.bucket_name, Delimiter="/", Prefix=prefix
        ):
            if result.get("CommonPrefixes") is not None:
                for subdir in result.get("CommonPrefixes"):
                    self.remove_stale_directories(
                        subdir.get("Prefix"), local_path, start_prefix
                    )
            if result.get("Contents") is not None:
                for file in result.get("Contents"):
                    key_relative = file.get("Key").replace(start_prefix, "")
                    # full_local_path = os.path.join(local_path, key_relative)
                    full_local_path = local_path + os.sep + key_relative

                    s3_path = file.get("Key")
                    exists = os.path.isfile(full_local_path)
                    if not exists:
                        self.client.delete_object(Bucket=self.bucket_name, Key=s3_path)
