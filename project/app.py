import connexion
import click
from flask.cli import AppGroup

# Assuming data_importer.py is in the same directory ('project')
from .data_importer import import_all_data as do_import_data

connex_app = connexion.App(__name__, specification_dir='../', server_args={'debug': True})
connex_app.add_api('openapi.yaml', base_path='/api/v1', resolver=connexion.resolver.RelativeResolver('project.api_handlers'))

app = connex_app.app

data_cli = AppGroup('data', help='Data management commands.')

@data_cli.command('import', help='Imports license and rule data from JSON files into the database.')
def import_data_command():
    click.echo("Starting data import via Flask CLI...")
    try:
        # Before running, the user should ensure 'licenses.db' is created by Liquibase.
        # A production system might check DB schema version here.
        do_import_data()
        click.echo("Data import finished.")
    except Exception as e:
        click.echo(f"Data import failed: {e}", err=True)
        import traceback
        traceback.print_exc()

app.cli.add_command(data_cli)

if __name__ == '__main__':
    connex_app.run(port=8080)
