# Copyright 2021 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import dataclass
from pathlib import PurePath

from pants.backend.go.target_types import GoBinaryMainAddress
from pants.backend.go.util_rules.build_go_pkg import BuildGoPackageRequest, BuiltGoPackage
from pants.backend.go.util_rules.link import LinkedGoBinary, LinkGoBinaryRequest
from pants.build_graph.address import Address, AddressInput
from pants.core.goals.package import (
    BuiltPackage,
    BuiltPackageArtifact,
    OutputPathField,
    PackageFieldSet,
)
from pants.engine.fs import AddPrefix, Digest, MergeDigests
from pants.engine.internals.selectors import Get
from pants.engine.rules import collect_rules, rule
from pants.engine.unions import UnionRule


@dataclass(frozen=True)
class GoBinaryFieldSet(PackageFieldSet):
    required_fields = (GoBinaryMainAddress,)

    main_address: GoBinaryMainAddress
    output_path: OutputPathField


@rule
async def package_go_binary(field_set: GoBinaryFieldSet) -> BuiltPackage:
    main_go_package_address = await Get(
        Address,
        AddressInput,
        AddressInput.parse(field_set.main_address.value, relative_to=field_set.address.spec_path),
    )

    built_package = await Get(
        BuiltGoPackage, BuildGoPackageRequest(main_go_package_address, is_main=True)
    )
    input_digest = await Get(
        Digest, MergeDigests([built_package.object_digest, built_package.imports_digest])
    )

    output_filename = PurePath(field_set.output_path.value_or_default(file_ending=None))

    binary = await Get(
        LinkedGoBinary,
        LinkGoBinaryRequest(
            input_digest=input_digest,
            archives=("./__pkg__.a",),
            import_config_path="./importcfg",
            output_filename=f"./{output_filename.name}",
            description=f"Link Go binary for {field_set.address}",
        ),
    )

    renamed_output_digest = await Get(
        Digest, AddPrefix(binary.output_digest, str(output_filename.parent))
    )

    artifact = BuiltPackageArtifact(relpath=str(output_filename))
    return BuiltPackage(digest=renamed_output_digest, artifacts=(artifact,))


def rules():
    return [*collect_rules(), UnionRule(PackageFieldSet, GoBinaryFieldSet)]
