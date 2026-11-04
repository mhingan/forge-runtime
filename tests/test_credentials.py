from forge_runtime.credentials import CredentialVault


def test_rejects_multiline_secret():
    try:
        CredentialVault().set("mcp/test/token", "one\ntwo")
    except ValueError:
        pass
    else:
        raise AssertionError("multiline secret was accepted")


def test_rejects_invalid_reference():
    try:
        CredentialVault().set("../bad", "secret")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid credential reference was accepted")
