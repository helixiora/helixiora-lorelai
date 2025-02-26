# alembic and flask-migrate

This app uses alembic for database migrations. Alembic and sqlalchemy are used to manage the
database schema. Models are defined in app/models.py and migrations are defined in this folder.

There's several operations that you regularly need to perform:

- Create a new database (if you're setting up the project for the first time)
- Create a new migration (when you add a new model or change a model)
- Apply migrations (when you update the codebase with someone else's changes and need to update the
  database schema)

## Create a new database

run `FLASK_APP=run.py flask init-db` to create the database and all the tables in it.

```terminal
> FLASK_APP=run.py flask init-db
Loading the app...
Initialized the database.
```

After that, you can run `FLASK_APP=run.py flask seed-db` to fill the database with some initial
data.

```terminal
> FLASK_APP=run.py flask seed-db
Loading the app...
Seeded the database.
```

## Create a new migration

run `FLASK_APP=run.py flask db migrate` to create a new migration file.

```terminal
> FLASK_APP=run.py flask db migrate
Loading the app...
```

## Apply migrations

## how this works

- in factory.py, we create the app and load flask-migrate by calling `migrate = Migrate(app, db)`
- in ./migrations/env.py, we load the sqlalchemy models so that alembic knows about them
- when we create a new migration, alembic will look at the models and generate a new set of changes
  to be applied to the database
- when we apply migrations, flask-migrate will run the generated migration files against the
  database to update it

## When you change models

When you make changes to the models in `app/models.py`, follow these steps:

1. Create a new migration:

```terminal
> FLASK_APP=run.py flask db migrate -m "Description of your model changes"
Loading the app...
INFO  [alembic.runtime.migration] Context impl MySQLImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.autogenerate] Detected added table 'new_table'
  Generating migrations/versions/xxxxxxxxxxxx_description_of_your_model_changes.py
```

1. Review the generated migration file in `migrations/versions/` to ensure it correctly captures
   your changes

1. Apply the migration:

```terminal
> FLASK_APP=run.py flask db upgrade
Loading the app...
INFO  [alembic.runtime.migration] Context impl MySQLImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade -> xxxxxxxxxxxx, Description of your model changes
```

1. If something goes wrong, you can roll back:

```terminal
> FLASK_APP=run.py flask db downgrade
```

Note: Always commit both your model changes and the generated migration files to version control.
