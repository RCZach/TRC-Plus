"""Individually inspected packed setters, pinned to code, layout and value limits.

Each accepted path updates one receiver-relative packed field, using a
masked OR or bounded scaled addition. Their full code matched the running exact build through read-only access.
Numeric bounds do not assign display names to unknown game IDs.
"""

import hashlib

from .roster import RosterError


SETTER_BUILD = '6ad2e48c:36532000'
# (field layout, maximum argument, code RVA, complete code size, code SHA-256)
SETTER_FIELDS = {
    ('accessories', 'Headband Frequency'): ((984, 3, 0, 'bits'), 4, 54922352, 171, 'b0e0f3f38fb28dfcd0e3ba5f1037453e87857b7ebba884d81da7cb61376a92f2'),
    ('accessories', 'Headband Logo Position'): ((1032, 3, 27, 'bits'), 6, 54921584, 176, 'dd236e4070015466b353d05e1607a461ab32a6ca8db56eeb8eb46f5b5b025d85'),
    ('appearance', 'Jersey Bagginess'): ((888, 4, 16, 'bits'), 10, 54922160, 176, '073d2195365a62b1afeffbe7767ad0cbeeffcb3304841994bd6cc8c979e572fa'),
    ('accessories', 'Left Ankle Frequency'): ((988, 3, 14, 'bits'), 4, 54925232, 176, '124686c62d174757449a2c94c67f3f379fc34c4e98ed7de3a34782c5a16153c7'),
    ('accessories', 'Left Ankle Item Away Color'): ((420, 3, 18, 'bits'), 7, 50091872, 176, '2bf10234ce3b7b90975188e8fb89cfe79f1e27c350ae0d95baff8e2881dd5453'),
    ('accessories', 'Left Ankle Item Home Color'): ((420, 3, 15, 'bits'), 7, 50091696, 176, '5f78fd6c47abddb56ae81f3427b113f6ec68e89ca7375f2c674e5d9ea4e84716'),
    ('accessories', 'Left Arm Frequency'): ((984, 3, 21, 'bits'), 4, 54924080, 176, 'a534f251592d09b6c0a6de409c359083c2ad880a40170a1842ef95b0df1b2d0e'),
    ('accessories', 'Left Arm Item Away Color'): ((404, 3, 14, 'bits'), 7, 50089760, 176, 'cb192746c7ef7c5b5ccaf2ab805cc82d32a95585be2613ea7cf23b5ec4dcba61'),
    ('accessories', 'Left Arm Item Home Color'): ((404, 3, 11, 'bits'), 7, 50089584, 176, 'a47c451a647a7d3c0f671163f9e7bbd67655be7976aea7fa6bd99f668217a070'),
    ('accessories', 'Left Elbow Frequency'): ((984, 3, 15, 'bits'), 4, 54923696, 176, '3947e55e8dfdcd4fde4e2ac67c5c90a0c78a780d705b0ff1e595b0e8d2ba2d80'),
    ('accessories', 'Left Elbow Item Home Color'): ((408, 3, 0, 'bits'), 7, 50088880, 171, '03dea07644801f28f852ab9b99de079a37296e743133c6cbd5a8c268f72e7072'),
    ('accessories', 'Left Fingers Frequency'): ((988, 3, 20, 'bits'), 4, 54922928, 176, 'd5f29e6757281c2c8b32fd2d15b77b4bf7f93efb15f2acb4344bb98548525551'),
    ('accessories', 'Left Fingers Item Home Color'): ((416, 3, 0, 'bits'), 7, 50092400, 171, '2f9da71a99340362668d485e4b08b58fc0b39db575d55f2c3fd683b24f1c2ccd'),
    ('accessories', 'Left Knee Frequency'): ((372, 3, 18, 'bits'), 4, 54924464, 176, '54e35dfedbbfa92abf9daaf46a9d654b9def8a36902b86c841ff4b46ca74281c'),
    ('accessories', 'Left Knee Item Home Color'): ((420, 3, 0, 'bits'), 7, 50090992, 171, 'f5278ee505190ce532422ff36a96050c0a964130fbc13c2f66caddbcabc54113'),
    ('accessories', 'Left Leg Frequency'): ((984, 3, 27, 'bits'), 4, 54924848, 176, '76b62fe40385b502814e890b3444b1b6e271e6647b4bb342a73e8f56d4c8e025'),
    ('accessories', 'Left Leg Item Away Color'): ((416, 3, 19, 'bits'), 7, 50090464, 176, 'a43d18dd7257cb412093908e06947d6d52eb6afaa87b949acbddc9917b2d7380'),
    ('accessories', 'Left Leg Item Home Color'): ((416, 3, 16, 'bits'), 7, 50090288, 176, '7b0009c7f5b9b1246d0a6fe93392e4a092370c68b3d115d6804f700622855f8f'),
    ('accessories', 'Left Wrist Frequency'): ((984, 3, 9, 'bits'), 4, 54923312, 176, '9bd90688cfec0b91b27a279d1da2fcdc233e685e32b66feef5f052d1a88098c0'),
    ('accessories', 'Left Wrist Item Away Color'): ((408, 5, 22, 'bits'), 16, 50088352, 176, '21fb97aee8e4d369a160954d08ea81fca1935f6c07e19359a4a9bd7e7aed883f'),
    ('accessories', 'Left Wrist Item Home Color'): ((408, 5, 17, 'bits'), 16, 50088176, 176, '83b31f07f9b4661869958a79db7d3526ff490760a124e36c2eadcfc81d25bee2'),
    ('gear', 'Preferred Shorts Type'): ((976, 3, 8, 'bits'), 3, 54921776, 176, '769e549b68802867aaf1cb8021d8c714e2e1f047b921d433faa96c09ac834b63'),
    ('accessories', 'Right Ankle Frequency'): ((988, 3, 17, 'bits'), 4, 54925424, 176, '576638c0e466994b51b863f066de17b150cb9c1cdb622ff07c6c276d9ee8a865'),
    ('accessories', 'Right Ankle Item Away Color'): ((420, 3, 27, 'bits'), 7, 50092224, 176, '4b67682f1a797e0dd519c9007fc1e34b26242464e78746b023a311ddf46f6f12'),
    ('accessories', 'Right Ankle Item Home Color'): ((420, 3, 24, 'bits'), 7, 50092048, 176, '16f7a69d2610fe2100c677859540870fee5902e538925a93c094dc744da13248'),
    ('accessories', 'Right Arm Frequency'): ((984, 3, 24, 'bits'), 4, 54924272, 176, 'f7919d1b7c055d42dd85298e866d9f936cdb36647283776318f22ac473a8c2a0'),
    ('accessories', 'Right Arm Item Away Color'): ((404, 3, 25, 'bits'), 7, 50090112, 176, 'af0532351c89978d3c95e0bda4553edfec2439d303471d7d791e321d7d8c2415'),
    ('accessories', 'Right Arm Item Home Color'): ((404, 3, 22, 'bits'), 7, 50089936, 176, 'cf517039f7927c5d1411ce212be8c4abc2d3ecf71f6b17a28e5e29ae553a8669'),
    ('accessories', 'Right Elbow Frequency'): ((984, 3, 18, 'bits'), 4, 54923888, 176, '3fb46281af8f4eed08693d9554cd4feb3d2ce26b1e933b1decc40f838f6b4117'),
    ('accessories', 'Right Elbow Item Away Color'): ((412, 3, 0, 'bits'), 7, 50089408, 171, 'b108968be1d0197b5a379d64e5b1942c723d6c6220a3d659b78f7cc8fc5c05ce'),
    ('accessories', 'Right Elbow Item Home Color'): ((408, 3, 10, 'bits'), 7, 50089232, 176, 'b5f9f6ba7a81809f6c2df1f6a8731889de43d7998f31dbc0d1d59b9a4ee9a952'),
    ('accessories', 'Right Fingers Frequency'): ((992, 3, 10, 'bits'), 4, 54923120, 176, 'ac8c31214e096cb962d702146599b5b2f547fe55cad36249daaf808b0aea27c3'),
    ('accessories', 'Right Fingers Item Away Color'): ((416, 3, 9, 'bits'), 7, 50092928, 176, 'e96fcb6ed9dd9dcbfe78e5dee6b50eb159c100b15d47b36dfb12c9e23cf4f935'),
    ('accessories', 'Right Fingers Item Home Color'): ((416, 3, 6, 'bits'), 7, 50092752, 176, '3cac483795a56cffcea1e249083968ca5a3716640405ad64003786b648b8ccc6'),
    ('accessories', 'Right Knee Frequency'): ((988, 3, 11, 'bits'), 4, 54924656, 176, '64ea7b44c02a215d0e8a04ab1cc9422d2b8ffca0fca80e9c76b2ff5e1ce41210'),
    ('accessories', 'Right Knee Item Away Color'): ((420, 3, 9, 'bits'), 7, 50091520, 176, '980befb15e25d63eec3089029e308239d343e14ceedcdbdf65417576988fb371'),
    ('accessories', 'Right Knee Item Home Color'): ((420, 3, 6, 'bits'), 7, 50091344, 176, '3e8250a06edea7fb05f9424fc4bc9c00163a2477f172101d692d8e3c2b5eb9d1'),
    ('accessories', 'Right Leg Frequency'): ((988, 3, 8, 'bits'), 4, 54925040, 176, '756bcda0ac12adace540a324b57c797e53938d37ea0fec75944a3c6f780ebbce'),
    ('accessories', 'Right Leg Item Away Color'): ((416, 3, 29, 'bits'), 7, 50090816, 176, '81da6a7ae310eb6690696eb4a9e26f7ca3bc2f6922a0674699e729a4108ead84'),
    ('accessories', 'Right Leg Item Home Color'): ((416, 3, 26, 'bits'), 7, 50090640, 176, '0f0a98e4f30f44777d095bcdd95411316bf0a5c0c6a999a608459afc88d71e49'),
    ('accessories', 'Right Wrist Frequency'): ((984, 3, 12, 'bits'), 4, 54923504, 176, 'c5336c694eeb4335e8256ef24eed4002b80d3cc461792f935246d447abe22b87'),
    ('accessories', 'Right Wrist Item Home Color'): ((408, 5, 27, 'bits'), 16, 50088528, 176, 'f181fdb38e6bbece8420ad8d9643642c9cdbf6a9faa4c24639265055526f9fa8'),
    ('gear', 'Shirts Items Away Color'): ((880, 3, 11, 'bits'), 7, 50087648, 176, '74e207ac461a3d11911b189fe42e16a445a6dca36383c95ce536822bd0ea48bf'),
    ('gear', 'Shirts Items Home Color'): ((976, 3, 24, 'bits'), 7, 50087472, 176, 'd4d00a0cb7e60baa70056752d909223e5e1c432bde1a5418a9503d0a15b081d4'),
    ('accessories', 'Shorts Item Frequency'): ((984, 3, 6, 'bits'), 4, 54922736, 176, '9f16f89ff03745aefe92464e36822c3a7dec6393dc60bc56b01009b7685133eb'),
    ('accessories', 'Shorts Items Home Color'): ((404, 3, 0, 'bits'), 7, 50087824, 171, '6c3af55607d47890b9ab197225d79cd1800eebeb9cb6f6a6d75b9202287b2025'),
    ('gear', 'Shorts Length'): ((1012, 4, 9, 'bits'), 10, 54921968, 176, 'ac8a1d5aa8fcc01ea30aeb05c5a347855c4d719134a717fb09c48f8e9a768530'),
    ('vitals', 'Skin Type'): ((476, 3, 0, 'bits'), 2, 54920688, 171, '7251f6408b81e092292764ca00f58222118a600f36faae67cd3e95760365736b'),
    ('accessories', 'Left Elbow Item Away Color'): ((408, 3, 3, 'bits'), 7, 50089056, 172, 'c062450edf84122049c9b41579a9897db2fca982dd374fb87c08afe4a1d888f7'),
    ('accessories', 'Left Fingers Item Away Color'): ((416, 3, 3, 'bits'), 7, 50092576, 172, '834674c50f57e6e4444a4b3e5eae616630e6860165d3c566b32f910439208185'),
    ('accessories', 'Left Knee Item Away Color'): ((420, 3, 3, 'bits'), 7, 50091168, 172, 'd944dfc32dbfb56256c53421aa848760ee633b9b2049a3208ee8ccc6b7dcf3c4'),
    ('gear', 'Shirts Item Frequency'): ((984, 3, 3, 'bits'), 4, 54922544, 172, 'cee573e14d372ed10b83535211013eb4c359505912c0576a98e90a879d8208af'),
    ('accessories', 'Shorts Items Away Color'): ((404, 3, 3, 'bits'), 7, 50088000, 172, 'b09f0d55bfd684b221c651478dfb1e974499dd11ecf3f9104d73dfec5bf54f60'),
    ('accessories', 'Right Wrist Item Away Color'): ((412, 5, 3, 'bits'), 16, 50088704, 174, 'b68f968bb6d954282cc2006180ab1747bca09361ccdb999932ad6384e2241e4b'),
    ('gear', 'Shoe Away Style'): ((388, 13, 13, 'bits'), 8191, 48290016, 424, '0c9f55fdf641c73e2a4d60d97db18ca5fdc63342dece99d3106525fc04336efe'),
}


def verified_setter_fields(process, profile):
    """Fail closed per field if the build, profile, range or native code changes."""
    if process.build.casefold() != SETTER_BUILD or profile.stride != 0x4F8:
        return set()
    enabled = set()
    checked = {}
    for key, (layout, maximum, rva, size, digest) in SETTER_FIELDS.items():
        field = profile.fields.get(key)
        if (not field or not field.writable or
                (field.offset, field.bits, field.shift, field.kind) != layout or
                (field.verified_build or '').casefold() != SETTER_BUILD or
                field.allowed_values != tuple(range(maximum + 1))):
            continue
        if rva not in checked:
            try:
                code = process.read(process.module_base + rva, size)
                checked[rva] = len(code) == size and hashlib.sha256(code).hexdigest() == digest
            except (RosterError, OSError):
                checked[rva] = False
        if checked[rva]:
            enabled.add(key)
    return enabled
