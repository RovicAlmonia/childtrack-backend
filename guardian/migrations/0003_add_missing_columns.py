from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('guardian', '0002_add_student_field'),
        ('parents', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql='''
            -- Add status column if missing (default 'pending')
            ALTER TABLE guardian_guardian
                ADD COLUMN IF NOT EXISTS status varchar(20) DEFAULT 'pending';

            -- Add student_id column if missing (parents.Student.lrn is a varchar primary key)
            ALTER TABLE guardian_guardian
                ADD COLUMN IF NOT EXISTS student_id varchar(20);

            -- Add FK constraint for student_id if it's not present
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'guardian_guardian_student_id_fkey'
                ) THEN
                    ALTER TABLE guardian_guardian
                        ADD CONSTRAINT guardian_guardian_student_id_fkey
                        FOREIGN KEY (student_id)
                        REFERENCES parents_student(lrn)
                        ON DELETE CASCADE;
                END IF;
            END
            $$;
            ''' ,
            reverse_sql="""-- Reverse intentionally left blank to avoid accidental data loss""",
        ),
    ]
