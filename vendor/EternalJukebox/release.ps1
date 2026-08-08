# Adapted from https://github.com/orhun/git-cliff/blob/main/release.sh

param(
    [Parameter(Mandatory = $True)]
    $VersionTag
)

Write-Host "Preparing $VersionTag"

try
{
    git cliff --config cliff.toml --tag "$VersionTag" -o CHANGELOG.md
    git add CHANGELOG.md
    git commit -m "chore(release): prepare for $VersionTag"

    $changelog = (git cliff --config release_tag.toml --unreleased --strip all) -join "`n"

    git tag -a "$VersionTag" -m "Release $VersionTag" -m "$changelog"
    git tag -v "$VersionTag"

    Write-Host "Done!"
    Write-Host "Now push the commit (git push) and the tag (git push --tags)."
}
catch
{
    Write-Error "Failed to generate CHANGELOG.md; is `git cliff` installed? (cargo binstall git-cliff)"
}