from enum import IntEnum


class Category(IntEnum):
    # Group BGM Categories
    Fields               = 0x00
    Towns                = 0x01
    Dungeons             = 0x02
    Indoors              = 0x03
    Minigames            = 0x04
    ActionThemes         = 0x05
    CalmThemes           = 0x06
    Fights               = 0x07

    # Group Fanfare Categories
    ItemFanfares         = 0x08
    EventFanfares        = 0x09
    ClearFanfares        = 0x10

    # Group Cutscene Categories
    Cutscenes            = 0x16

    # Individual BGM Categories
    TerminaField         = 0x102
    PursuitTheme         = 0x103
    MajorasTheme         = 0x104
    ClockTower           = 0x105
    StoneTower           = 0x106
    InvertedStoneTower   = 0x107
    HealingTheme         = 0x10B
    SouthernSwamp        = 0x10C
    AliensTheme          = 0x10D
    BoatCruise           = 0x10E
    SharpsCurse          = 0x10F
    GreatBay             = 0x110
    IkanaCanyon          = 0x111
    DekuPalace           = 0x112
    Snowhead             = 0x113
    PiratesFortress      = 0x114
    ClockTown1           = 0x115
    ClockTown2           = 0x116
    ClockTown3           = 0x117
    FileSelect           = 0x118
    SmallEnemy           = 0x11A
    BossEnemy            = 0x11B
    BossBattle           = 0x11B  # Alias
    WoodfallTemple       = 0x11C
    House                = 0x11F
    MinigameTheme        = 0x125
    GoronRace            = 0x126
    MusicBoxHouse        = 0x127
    GreatFairysFountain  = 0x128
    FairysFountain       = 0x128  # Alias
    ZeldasTheme          = 0x129
    RosaSistersTheme     = 0x12A
    CuriosityShop        = 0x12C
    MarineResearchLab    = 0x12C  # Alias
    GiantsTheme          = 0x12D
    GuruGurusTheme       = 0x12E
    RomaniRanch          = 0x12F
    GoronShrine          = 0x130
    MayorsOffice         = 0x131
    ZoraHall             = 0x136
    BigEnemy             = 0x138
    MinibossBattle       = 0x138  # Alias
    AstralObservatory    = 0x13A
    SecretGrotto         = 0x13B
    MilkBar              = 0x13C
    WoodsOfMystery       = 0x13E
    MysteryWoods         = 0x13E  # Alias
    HorseRace            = 0x140
    GormanBrosTheme      = 0x142
    WitchesTheme         = 0x143
    KoumeAndKotakesTheme = 0x143  # Alias
    ItemShop             = 0x144
    OwlsTheme            = 0x145
    KaeporaGaeborasTheme = 0x145  # Alias
    MinigameShop         = 0x146
    SwordSchool          = 0x150
    FinalHours           = 0x157
    SnowheadTemple       = 0x165
    GreatBayTemple       = 0x166
    MajorasWrath         = 0x169
    MajorasIncarnation   = 0x16A
    MajorasMask          = 0x16B
    JapasRoom            = 0x16C
    TijosRoom            = 0x16D
    EvansRoom            = 0x16E
    IkanaCastle          = 0x16F
    KamarosTheme         = 0x171
    CremiasTheme         = 0x172
    KeatonsTheme         = 0x173
    MoonEnraged          = 0x17B
    ReunionTheme         = 0x17D

    # Individual Fanfare Categories
    EventFail1           = 0x108
    EventFail2           = 0x109
    EventSuccess         = 0x119
    GameOver             = 0x120
    BossDefeated         = 0x121
    ItemGet              = 0x122
    HeartContainerGet    = 0x124
    OpenChest            = 0x12B
    MaskGet              = 0x137
    HeartPieceGet        = 0x139
    TruthRevealed        = 0x13D
    GoronRaceWin         = 0x13F
    HorseRaceWin         = 0x141
    SongGet              = 0x152
    SoaringTheme         = 0x155
    TempleAppears        = 0x177
    TempleClearShort     = 0x178
    TempleClearLong      = 0x179
    GiantsLeave          = 0x17C
    MoonDestroyed        = 0x17E

    # Individual Cutscene Categories
    GiantsAppear         = 0x170
    TitleDemo            = 0x176

if __name__ == '__main__':
    print('This is a utility script meant to be used with the MMRS Music Updater main script. On its own it has no functionality.')
