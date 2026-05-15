"""checkpoint_1

Revision ID: 9f150e4f9a05
Revises: 53502b6d63bf
Create Date: 2025-05-21 12:25:55.556388

"""
import datetime

from alembic.operations import Operations
import sqlalchemy as sa
import mindsdb.interfaces.storage.db  # noqa


# revision identifiers, used by Alembic.
revision = '9f150e4f9a05'
down_revision = '53502b6d63bf'
branch_labels = None
depends_on = None


def upgrade(op: Operations = None):
    # region skip migration if it is existing app, apply if it is new app
    if op is None:
        # 'op' is passed only from migrate.py when applying checkpoin migration
        return
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if 'alembic_version' in inspector.get_table_names():
        # If version_num exists, then it is existing app
        result = connection.execute(sa.text("SELECT version_num FROM alembic_version"))
        current_version = result.scalar()
        if current_version is not None:
            return
    # endregion

    op.create_table(
        'agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('user_class', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(), nullable=True),
        sa.Column('provider', sa.String(), nullable=True),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'chat_bots_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_bot_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('text', sa.String(), nullable=True),
        sa.Column('user', sa.String(), nullable=True),
        sa.Column('destination', sa.String(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'file',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('source_file_path', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('columns', mindsdb.interfaces.storage.db.Json(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'company_id', name='unique_file_name_company_id')
    )
    op.create_table(
        'integration',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('engine', sa.String(), nullable=False),
        sa.Column('data', mindsdb.interfaces.storage.db.Json(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'company_id', name='unique_integration_name_company_id')
    )
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('user_class', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('query_str', sa.String(), nullable=False),
        sa.Column('if_query_str', sa.String(), nullable=True),
        sa.Column('start_at', sa.DateTime(), nullable=True),
        sa.Column('end_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('schedule_str', sa.String(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'jobs_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('query_str', sa.String(), nullable=True),
        sa.Column('start_at', sa.DateTime(), nullable=True),
        sa.Column('end_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'start_at', name='uniq_job_history_job_id_start')
    )
    op.create_table(
        'json_storage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_group', sa.String(), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('encrypted_content', sa.LargeBinary(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'llm_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('input', sa.String(), nullable=False),
        sa.Column('output', sa.String(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'llm_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('api_key', sa.LargeBinary(), nullable=True),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('model_group', sa.String(), nullable=True),
        sa.Column('input', sa.JSON(), nullable=True),
        sa.Column('output', sa.JSON(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('cost', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('exception', sa.String(), nullable=True),
        sa.Column('traceback', sa.String(), nullable=True),
        sa.Column('stream', sa.Boolean(), nullable=True, comment="Is this completion done in 'streaming' mode"),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'project',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'company_id', name='unique_project_name_company_id')
    )
    op.create_table(
        'queries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('sql', sa.String(), nullable=False),
        sa.Column('database', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('processed_rows', sa.Integer(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'query_context',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('context_name', sa.String(), nullable=False),
        sa.Column('values', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('user_class', sa.Integer(), nullable=True),
        sa.Column('object_type', sa.String(), nullable=False),
        sa.Column('object_id', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('reload', sa.Boolean(), nullable=True),
        sa.Column('run_by', sa.String(), nullable=True),
        sa.Column('alive_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'triggers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('database_id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(), nullable=False),
        sa.Column('query_str', sa.String(), nullable=False),
        sa.Column('columns', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'agent_skills',
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ),
        sa.PrimaryKeyConstraint('agent_id', 'skill_id')
    )
    op.create_table(
        'chat_bots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('model_name', sa.String(), nullable=True),
        sa.Column('database_id', sa.Integer(), nullable=True),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('webhook_token', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], name='fk_agent_id'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'predictor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('data', mindsdb.interfaces.storage.db.Json(), nullable=True),
        sa.Column('to_predict', mindsdb.interfaces.storage.db.Array(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('mindsdb_version', sa.String(), nullable=True),
        sa.Column('native_version', sa.String(), nullable=True),
        sa.Column('integration_id', sa.Integer(), nullable=True),
        sa.Column('data_integration_ref', mindsdb.interfaces.storage.db.Json(), nullable=True),
        sa.Column('fetch_data_query', sa.String(), nullable=True),
        sa.Column('learn_args', mindsdb.interfaces.storage.db.Json(), nullable=True),
        sa.Column('update_status', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('training_data_columns_count', sa.Integer(), nullable=True),
        sa.Column('training_data_rows_count', sa.Integer(), nullable=True),
        sa.Column('training_start_at', sa.DateTime(), nullable=True),
        sa.Column('training_stop_at', sa.DateTime(), nullable=True),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(), nullable=True),
        sa.Column('lightwood_version', sa.String(), nullable=True),
        sa.Column('dtype_dict', mindsdb.interfaces.storage.db.Json(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('training_phase_current', sa.Integer(), nullable=True),
        sa.Column('training_phase_total', sa.Integer(), nullable=True),
        sa.Column('training_phase_name', sa.String(), nullable=True),
        sa.Column('training_metadata', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['integration_id'], ['integration.id'], name='fk_integration_id'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], name='fk_project_id'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('predictor', schema=None) as batch_op:
        batch_op.create_index('predictor_index', ['company_id', 'name', 'version', 'active', 'deleted_at'], unique=True)

    op.create_table(
        'view',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], name='fk_project_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'company_id', name='unique_view_name_company_id')
    )
    op.create_table(
        'knowledge_base',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('vector_database_id', sa.Integer(), nullable=True),
        sa.Column('vector_database_table', sa.String(), nullable=True),
        sa.Column('embedding_model_id', sa.Integer(), nullable=True),
        sa.Column('query_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['embedding_model_id'], ['predictor.id'], name='fk_knowledge_base_embedding_model_id'),
        sa.ForeignKeyConstraint(['vector_database_id'], ['integration.id'], name='fk_knowledge_base_vector_database_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'project_id', name='unique_knowledge_base_name_project_id')
    )

    # Insert default project
    op.bulk_insert(
        sa.table(
            'project',
            sa.Column('name', sa.String()),
            sa.Column('company_id', sa.Integer()),
            sa.Column('metadata', sa.JSON()),
            sa.Column('created_at', sa.DateTime())
        ),
        [{
            'name': 'mindsdb',
            'company_id': 0,
            'metadata': {'is_default': True},
            'created_at': datetime.datetime.now()
        }]
    )


def downgrade():
    # do nothging, since it is checkpoint migration
    pass
