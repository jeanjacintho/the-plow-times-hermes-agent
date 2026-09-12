# The Plow Times' own image: the pinned Plow cloud base plus the PDF
# toolchain the edition renderer needs.
#
# Why this exists. The base image ships no HTML-to-PDF engine: measured
# inside a running the-plow-times container, `import weasyprint` is a
# ModuleNotFoundError, and there is no `reportlab`/`pypdf` either, no Chrome
# and no wkhtmltopdf. So `render_edition.py --pdf` fails by design there, and
# the agent correctly told its owner it could not produce the paper as a PDF.
# Installing weasyprint is what makes the PDF leg of the fixed template real,
# container-side, with no dependency on a browser on the owner's Mac.
#
# Pinned by digest, exactly like the fleet's `runtime/stack.json`: a mutable
# tag would re-resolve on every pull and change a large unreviewed surface
# under a running agent that holds live credentials. Bump both together.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents@sha256:bfd4980f361a551e62569f8c2eb717c1076d0b8be3a0499b869eaece151336a4

# WeasyPrint's native dependencies. The Python wheel is pure Python but binds
# Pango/Cairo through cffi at import time, so the shared libraries have to be
# present or `import weasyprint` fails with a cffi error that reads like a
# Python problem. Debian 13 (trixie) is the base's own distro; these are its
# package names. fonts-dejavu-core gives the rendered page a guaranteed font
# even with no fontconfig cache, so a fresh container never prints blanks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 \
      libpangocairo-1.0-0 \
      libpangoft2-1.0-0 \
      libharfbuzz0b \
      libcairo2 \
      libgdk-pixbuf-2.0-0 \
      libffi8 \
      shared-mime-info \
      fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Install into the SYSTEM python, because that is what the skill runs:
# `python3 ../../pt-edition/scripts/render_edition.py ...` resolves to
# /usr/bin/python3, and a package in a private venv would be invisible to it.
# The base is PEP 668 externally-managed, and `uv` (present in the base, used
# by sibling images) installs past that with --break-system-packages. The
# import check fails the build rather than shipping an image whose PDF leg is
# a promise it cannot keep.
ARG WEASYPRINT_VERSION=62.3
RUN uv pip install --system --break-system-packages \
      "weasyprint==${WEASYPRINT_VERSION}" \
 && python3 -c "import weasyprint; print('weasyprint', weasyprint.__version__)"
