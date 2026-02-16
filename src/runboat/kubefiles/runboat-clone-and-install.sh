#!/bin/bash

set -exo pipefail

# Remove initialization sentinel and data, in case we are reinitializing.
rm -fr /mnt/data/*

# Remove addons dir, in case we are reinitializing after a previously
# failed installation.
rm -fr $ADDONS_DIR
# Download the repository at git reference into $ADDONS_DIR.
# We use curl instead of git clone because the git clone method used more than 1GB RAM,
# which exceeded the default pod memory limit.
mkdir -p $ADDONS_DIR
cd $ADDONS_DIR

if [[ "${RUNBOAT_PLATFORM}" == "gitlab" ]]; then
    # GitLab archive API: /projects/:id/repository/archive.tar.gz?sha=:ref
    # Use project_id if available, otherwise URL-encode the repo path
    if [[ -n "${RUNBOAT_PROJECT_ID}" ]]; then
        ARCHIVE_URL="${RUNBOAT_GITLAB_URL}/api/v4/projects/${RUNBOAT_PROJECT_ID}/repository/archive.tar.gz?sha=${RUNBOAT_GIT_REF}"
    else
        ENCODED_REPO=$(echo "${RUNBOAT_GIT_REPO}" | sed 's|/|%2F|g')
        ARCHIVE_URL="${RUNBOAT_GITLAB_URL}/api/v4/projects/${ENCODED_REPO}/repository/archive.tar.gz?sha=${RUNBOAT_GIT_REF}"
    fi
    # Use Bearer auth if RUNBOAT_GITLAB_TOKEN is set (for private repos)
    if [[ -n "${RUNBOAT_GITLAB_TOKEN}" ]]; then
        curl -sSL -H "Authorization: Bearer ${RUNBOAT_GITLAB_TOKEN}" "${ARCHIVE_URL}" | tar zxf - --strip-components=1
    else
        curl -sSL "${ARCHIVE_URL}" | tar zxf - --strip-components=1
    fi
else
    # GitHub tarball URL
    curl -sSL https://github.com/${RUNBOAT_GIT_REPO}/tarball/${RUNBOAT_GIT_REF} | tar zxf - --strip-components=1
fi

# Install.
INSTALL_METHOD=${INSTALL_METHOD:-oca_install_addons}
if [[ "${INSTALL_METHOD}" == "oca_install_addons" ]] ; then
    oca_install_addons
elif [[ "${INSTALL_METHOD}" == "editable_pip_install" ]] ; then
    pip install -e .
else
    echo "Unsupported INSTALL_METHOD: '${INSTALL_METHOD}'"
    exit 1
fi

# Keep a copy of the venv that we can re-use for shorter startup time.
cp -ar /opt/odoo-venv/ /mnt/data/odoo-venv

touch /mnt/data/initialized
