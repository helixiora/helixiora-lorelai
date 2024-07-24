# Operating procedures

## Allowing a new user to register to Lorelai

Until we come out of test stage, we need to add individual users to the Google Cloud Project in
order to allow them to sign in. Once the project is published, this won't be necessary anymore.

1. Sign into [Google Cloud console](https://console.cloud.google.com/apis/credentials/consent)
1. Add the user's email address to the list of Test users

## Adding a new user to an existing organisation

When you want to add a new user to an existing organisation you can't ask them to sign up because
they won't be able to join an existing org. Soon we will have invite functionality, but until then:

1. Log into AWS console and go to the AWS account that the lorelai instance is running in to which
   you want to add a user

1. Start the cloud shell, and connect to the RDS instance (look up the RDS endpoint first):
   `$ mysql -uadmin -p -h<<your-rds-endpoint>>`

1. Add the user to the `user` table:

   ```sql
   INSERT INTO user (org_id, user_name, email, slack_token, full_name, google_id)
   VALUES (1, '<<>username>>', '<<email>>', NULL, '<<fullname>>', '<<google id>>');
   ```

1. check the user_id of the new user, and the role_id of the role you want to give them:

   ```sql
   MariaDB [lorelai]> select * from user;
   +---------+--------+--------------------+--------------------------+-------------+---------------
   -----+-----------------------+
   | user_id | org_id | user_name          | email                    | slack_token | full_name
        | google_id             |
   +---------+--------+--------------------+--------------------------+-------------+---------------
   -----+-----------------------+
   |       1 |      1 | john               | john@helixiora.com       | NULL        | John Doe
        | 892374623894627237737 |
   |       2 |      1 | jane               | jane@helixiora.com       | NULL        | Jane Johnsson
        | 373773739723948493874 |
   +---------+--------+--------------------+--------------------------+-------------+---------------
   -----+-----------------------+
   2 rows in set (0.001 sec)

   MariaDB [lorelai]> select * from roles;
   +---------+-------------+
   | role_id | role_name   |
   +---------+-------------+
   |       2 | org_admin   |
   |       1 | super_admin |
   |       3 | user        |
   +---------+-------------+
   3 rows in set (0.001 sec)
   ```

1. Insert a record in `user_roles`:

   ```sql
   insert into user_roles(user_id, roled_id) values (x, y);
   ```

Now the user should be able to log in normally
