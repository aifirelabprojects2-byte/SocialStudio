# Install honcho
RUN pip install honcho
# Override CMD for multi-process
CMD ["honcho", "start", "-f", "Procfile"]