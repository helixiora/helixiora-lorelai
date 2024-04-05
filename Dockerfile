# We can use any version of Python here
FROM python:3.10

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN chmod +x indexer.py lorelaicli.py

# Make port 5000 available 
EXPOSE 5001

# Run app.py when the container launches
CMD ["python", "app.py"]

