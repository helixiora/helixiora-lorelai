# Use an explicit version of Python for consistent builds. Consider using slim variant for reduced size.
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy only the files needed for pip install to avoid cache busting the layer if unrelated files change.
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
# Consider using --upgrade pip and a virtual environment for even better practice.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application's code into the container
COPY . .

# Only make the scripts executable if they aren't already. If they are, this step can be omitted.
RUN chmod +x indexer.py lorelaicli.py

# Make port 5000 available to the world outside this container
# EXPOSE 5000

# Use exec form of CMD to make sure Python is run directly and receives UNIX signals
CMD ["python", "run.py"]
