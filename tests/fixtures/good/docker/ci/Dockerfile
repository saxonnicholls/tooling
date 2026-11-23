#
#  Dockerfile
#  snicholls-tooling test fixture
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The fixture's own image, derived from tooling's standard one, as a repository that needs a library adds it (an
#  OpenCL repository installs PoCL here). The gate passes the standard image it builds as TOOLING_IMAGE. The marker
#  file is what the image.derived CTest looks for, so the configuration that names this image proves it ran in it.

ARG TOOLING_IMAGE
FROM ${TOOLING_IMAGE}
RUN echo "snicholls-fixture derived image" > /etc/snicholls-fixture-image
