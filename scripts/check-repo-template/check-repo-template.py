#!/usr/bin/env python3

import subprocess
import shutil
import os
import re
import pytoml


riscv_repos = [
    "rust-embedded/riscv-rt",
    "rust-embedded/riscv",
    "riscv-rust/e310x",
    "riscv-rust/e310x-hal",
    "riscv-rust/hifive1",
    "riscv-rust/riscv-rust-quickstart",
    "riscv-rust/k210-pac",
    "riscv-rust/k210-hal",
    "riscv-rust/k210-example",
    "riscv-rust/k210-crates",
]

teams = {
    'riscv': {'name': 'RISC-V team', 'link': 'https://github.com/rust-embedded/wg#the-riscv-team', 'email': 'The RISC-V Team <risc-v@teams.rust-embedded.org>'}
}

readme_template = open("template/README.md", "rt").read()
coc_template = open("template/CODE_OF_CONDUCT.md", "rt").read()


def parse_md_str(data):
    content = {}
    current_header = ""
    accumulated = []
    for line in data.split("\n"):
        if re.match("^#+ ", line):
            content[current_header] = accumulated
            current_header = line
            accumulated = []
            continue
        accumulated.append(line)
    content[current_header] = accumulated

    return content


def parse_md(path):
    f = open(path, "rt")
    data = f.read()
    f.close()
    return parse_md_str(data)


def strip_chapter(chapter):
    while len(chapter) > 0 and chapter[0] == '':
        chapter = chapter[1:]
    while len(chapter) > 0 and chapter[-1] == '':
        chapter = chapter[:-1]
    return chapter


def get_crate_name(repo):
    return repo.split("/")[-1]


def get_team_id(repo):
    return 'riscv'


def check_links_section(chapter, repo, crate_name):
    chapter = strip_chapter(chapter)

    if len(chapter) > 3:
        print("Unexpected lines in links section:")
        for line in chapter[3:]:
            print("  %s" % line)
    if len(chapter) < 3:
        print("Not enough lines in links section:")
        for line in chapter:
            print("  %s" % line)
        return

    links = [
        "[![crates.io](https://img.shields.io/crates/d/@CRATE@.svg)](https://crates.io/crates/@CRATE@)",
        "[![crates.io](https://img.shields.io/crates/v/@CRATE@.svg)](https://crates.io/crates/@CRATE@)",
        "[![Build Status](https://travis-ci.org/@REPO@.svg?branch=master)](https://travis-ci.org/@REPO@)",
    ]
    links = map(lambda s: s.replace("@CRATE@", crate_name).replace("@REPO@", repo), links)
    for i, link in enumerate(links):
        readme_link = chapter[i]
        if readme_link != link:
            print("Wrong link:")
            print("    Actual:", readme_link)
            print("  Expected:", link)


def parse_toml(repo_dir, repo):
    path = os.path.join(repo_dir, 'Cargo.toml')
    if not os.path.exists(path):
        print("Repo contains no Cargo.toml!")
        return
    f = open(path, 'rt')
    toml = pytoml.load(f)
    f.close()

    data = {}
    if 'workspace' in toml:
        data['workspace'] = True
        return data
    data['workspace'] = False
    package = toml['package']
    #print(package)

    team = teams[get_team_id(repo)]

    data['name'] = package['name']
    if team['email'] not in package['authors']:
        print("Team email is not listed in package authors:")
        print(" ", package['authors'])
    if 'description' not in package:
        print("Cargo.toml does not have 'description'")
        data['description'] = ""
    else:
        data['description'] = package['description']
    if 'categories' not in package:
        print("Cargo.toml does not have 'categories'")
    if 'keywords' not in package:
        print("Cargo.toml does not have 'keywords'")
    if 'license' not in package:
        print("Cargo.toml does not have 'license'")
    return data


def check_readme(repo_dir, repo, cargo_toml):
    path = os.path.join(repo_dir, 'README.md')
    if not os.path.exists(path):
        print("Repo contains no README.md!")
        return

    team = teams[get_team_id(repo)]
    crate_name = get_crate_name(repo)
    description = cargo_toml['description']

    target_readme = readme_template.replace("@CRATE@", crate_name).replace("@REPO@", repo).replace("@DESCRIPTION@", description)
    target_readme = target_readme.replace('@TEAM_NAME@', team['name']).replace('@TEAM_LINK@', team['link'])
    target_chapters = parse_md_str(target_readme)

    chapters = parse_md(path)

    target_headers = sorted(target_chapters.keys())
    headers = sorted(chapters.keys())
    if target_headers != headers:
        missing = sorted(set(target_headers).difference(set(headers)))
        if len(missing) > 0:
            print("Missing chapters:")
            for s in missing:
                print("  %s" % s)
        extra = sorted(set(headers).difference(set(target_headers)))
        if len(extra) > 0:
            print("Extra chapters:")
            for s in extra:
                print("  %s" % s)
    common = sorted(set(headers).intersection(set(target_headers)))
    for s in common:
        target_chapter = strip_chapter(target_chapters[s])
        chapter = strip_chapter(chapters[s])
        if target_chapter != chapter:
            print("Chapter %s differs" % s)
            if len(target_chapter) != len(chapter):
                print(target_chapter)
                print(chapter)
            else:
                if "License" in s:
                    continue
                for i in range(len(target_chapter)):
                    target_line = target_chapter[i]
                    line = chapter[i]
                    if target_line != line:
                        print("   Wrong:", line)
                        print(" Correct:", target_line)
                        print()


def clone_and_check_repo(repo):
    url = "https://github.com/" + repo + ".git"
    print("\n\n==>", repo)
    repo_dir = os.path.join("repos", repo.replace("/", "_"))

    if not os.path.exists(repo_dir):
        subprocess.check_output(["git", "clone", url, repo_dir], stderr=subprocess.STDOUT)

    cargo_toml = parse_toml(repo_dir, repo)
    check_readme(repo_dir, repo, cargo_toml)


def main():
    for repo in riscv_repos:
        clone_and_check_repo(repo)


if __name__ == "__main__":
    main()
