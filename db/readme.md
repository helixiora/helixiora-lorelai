### README: Database Versioning with Flyway for Lorelai

#### **Why Flyway?**
Flyway is a version control tool specifically designed for databases. It allows us to track, version, and deploy database changes safely and predictably across development, staging, and production environments. By using Flyway, we can:

- **Automate Database Migrations:** Automatically apply changes to the database schema, making it easier to sync environments.
- **Track Schema Versions:** Maintain a history of schema changes, enabling easier rollback and understanding of evolution.
- **Collaborate Efficiently:** Coordinate better among team members, avoiding conflicts in database structures.

#### **Getting Started with Flyway in Lorelai**

##### Prerequisites:
- MySQL database
- Python development environment

##### Initial Setup:

1. **Install Flyway:**

   Download Flyway from [Flyway Official Website](https://flywaydb.org/download/) and follow the installation instructions suitable for your OS.

2. **Clone the Repository:**

   Ensure you have the latest version of the Lorelai project by cloning the repo from our Git repository.

3. **Configure Flyway:**

   Navigate to the Flyway conf file (`conf/flyway.conf`) in your project directory and configure it to connect to your local MySQL instance:
     ```
     flyway.url=jdbc:mysql://localhost:3306/lorelai
     flyway.user=yourUsername
     flyway.password=yourPassword
     ```
    Note: a `flyway.conf.example` is included in the project for inspiration and ease of use.

4. **Baseline the Database:**

   If setting up a new development environment, import the baseline schema:
     ```bash
     mysql -u username -p lorelai < baseline_schema.sql
     ```

5. **Apply Migrations:**

   Apply any existing migrations to your local database:
     ```bash
     flyway migrate
     ```

#### **Making Changes to the Database Schema**

To make and track changes to the database schema, follow these steps:

1. **Create a New Migration File:**
   - In the `./db/migration` directory, create a new migration file for your changes. Name it according to Flyway's versioning conventions (e.g., `V1.2__Add_new_column_to_table.sql`).
   - Write the necessary SQL statements in this file. This can be an alter table, an insert (for system data) or pretty much anything else.

2. **Test Locally:**
   - Before pushing your changes, make sure to test them locally:
     ```bash
     flyway migrate
     ```

3. **Commit and Push:**
   - After successful local testing, commit your migration script to the repository and push it to the main branch.

4. **Track and Discuss:**
   - Use our #engineering channel on Slack to discuss changes and track progress through ClickUp tasks.

#### **Need Help?**
If you encounter any issues or need assistance with database migrations, please post your queries in the #engineering channel on Slack or create a task in ClickUp.

By following these guidelines, we ensure that all changes to the database schema are managed effectively and consistently across all environments. Happy coding, and let's make Lorelai better together!
