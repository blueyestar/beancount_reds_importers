#!/usr/bin/env python3

"""Download account statements automatically when possible, or display a reminder of how to download them.
Multi-threaded."""

# TODO:
# - autocomplete sites from command line
# - subcommand to generate an initial download.cfg file

import click
from click_aliases import ClickAliasedGroup
import os
import configparser
import asyncio


@click.group(cls=ClickAliasedGroup)
def cli():
    """Download account statements automatically when possible, or display a reminder of how to download them.
    Multi-threaded."""
    pass


def readConfigFile(configfile):
    config = configparser.ConfigParser()
    # config.optionxform = str # makes config file case sensitive
    config.read(os.path.expandvars(configfile))
    return config


def get_sites(sites, t, config):
    return [s for s in sites if config[s]['type'] == t]


@cli.command(aliases=['list'])
@click.option('-c', '--config-file', envvar='BEAN_DOWNLOAD_CONFIG', required=True, help='Config file',
              type=click.Path(exists=True))
@click.option('-s', '--sort', is_flag=True, help='Sort output')
def list_institutions(config_file, sort):
    """List institutions (sites) currently configured."""
    config = readConfigFile(config_file)
    all_sites = config.sections()
    types = set([config[s]['type'] for s in all_sites])
    for t in sorted(types):
        sites = get_sites(all_sites, t, config)
        if sort:
            sites = sorted(sites)
        name = f"{t} ({len(sites)})".ljust(14)
        print(f"{name}:", end='')
        print(*sites, sep=', ')
        print()


@cli.command()
@click.option('-c', '--config-file', envvar='BEAN_DOWNLOAD_CONFIG', required=True, help='Config file')
@click.option('--sites', help="Sites to downlad; unspecified means all", default='')
@click.option('--site_type', help="Download all sites in specified type", default='')
@click.option('--dry-run', is_flag=True, help="Do not actually download", default=False)
@click.option('--verbose', is_flag=True, help="Verbose", default=False)
def download(config_file, sites, site_type, dry_run, verbose):
    """Download statements for the specified institutions (sites)."""
    config = readConfigFile(config_file)
    if sites:
        sites = sites.split(',')
    else:
        sites = config.sections()
        if site_type:
            sites = get_sites(sites, site_type, config)

    errors = []
    success = []
    numsites = len(sites)
    print(f"{numsites} to process.")

    async def download_site(i, site):
        tid = f'[{i+1}/{numsites} {site}]'
        print(f'{tid}: Begin')
        options = config[site]
        # We support cmd and display, and type to filter
        if 'display' in options:
            print(f"{tid}: {options['display']}")
        if 'cmd' in options:
            cmd = os.path.expandvars(options['cmd'])
            if verbose:
                print(f"{tid}: Executing: {cmd}")
            if dry_run:
                await asyncio.sleep(2)
            else:
                # https://docs.python.org/3.8/library/asyncio-subprocess.html#asyncio.create_subprocess_exec
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    errors.append(site)
                else:
                    success.append(site)
                    print(f"{tid}: Success")

    async def perform_downloads(sites):
        tasks = [download_site(i, site) for i, site in enumerate(sites)]
        await asyncio.gather(*tasks)

    asyncio.run(perform_downloads(sites))

    if errors:
        print(f"Successful sites: {success}.")
        print()
        print(f"Unsuccessful sites: {errors}.")
    else:
        print(f"{len(success)} Downloads successful:", ','.join(success))


if __name__ == '__main__':
    cli()
