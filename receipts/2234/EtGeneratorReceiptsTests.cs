// Earned Trust — catching tests written by the REVIEWER (not the author agent) for ju26-issue-2234.
// Copied into tests/MessagePack.SourceGenerator.Tests/ of both the BASE and HEAD worktrees.
// A test that fails on BASE and passes on HEAD is a *proven* behavior change.
// The generated formatter text is written to $ET_EVIDENCE_DIR so the human can see the real output at reveal time.
#nullable enable

using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.Testing;

namespace MessagePack.SourceGenerator.Tests;

public class EtGeneratorReceiptsTests
{
    private readonly ITestOutputHelper logger;

    public EtGeneratorReceiptsTests(ITestOutputHelper logger) => this.logger = logger;

    private const string DuplicateIntKeys = """
        using MessagePack;
        [MessagePackObject]
        public class Foo
        {
            [Key(0)] public int First { get; set; }
            [Key(0)] public int Second { get; set; }
        }
        """;

    private const string DuplicateStringKeys = """
        using MessagePack;
        [MessagePackObject]
        public class Foo
        {
            [Key("a")] public int First { get; set; }
            [Key("a")] public int Second { get; set; }
        }
        """;

    private const string MixedKeys = """
        using MessagePack;
        [MessagePackObject]
        public class Foo
        {
            [Key(0)] public int First { get; set; }
            [Key("b")] public int Second { get; set; }
        }
        """;

    /// <summary>Runs the MessagePack source generator on <paramref name="source"/> and returns (exception, formatter source for Foo).</summary>
    private async Task<(System.Exception? Error, string? Formatter)> RunGeneratorAsync(string source, string evidenceName)
    {
        var refs = await ReferenceAssemblies.Net.Net80.ResolveAsync(LanguageNames.CSharp, CancellationToken.None);
        var parse = new CSharpParseOptions(LanguageVersion.Latest);
        var compilation = CSharpCompilation.Create(
            "EtReceipts",
            new[] { CSharpSyntaxTree.ParseText(source, parse) },
            refs.AddRange(ReferencesHelper.GetReferences(ReferencesSet.MessagePack)),
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));

        GeneratorDriver driver = CSharpGeneratorDriver.Create(
            new[] { new MessagePackGenerator().AsSourceGenerator() }, parseOptions: parse);
        driver = driver.RunGenerators(compilation);
        var result = driver.GetRunResult().Results.Single();

        string? formatter = result.GeneratedSources
            .Where(s => s.HintName.Contains("FooFormatter"))
            .Select(s => s.SourceText.ToString())
            .FirstOrDefault();

        string report = result.Exception is not null
            ? $"GENERATOR THREW: {result.Exception.GetType().Name}: {result.Exception.Message}"
            : formatter ?? "(no formatter generated for Foo)";
        this.logger.WriteLine(report);
        string? dir = System.Environment.GetEnvironmentVariable("ET_EVIDENCE_DIR");
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, evidenceName + ".txt"), report);
        }

        return (result.Exception, formatter);
    }

    private static void AssertNoCrash(System.Exception? error)
    {
        if (error is not null)
        {
            Assert.Fail($"GENERATOR THREW: {error.GetType().Name}: {error.Message}");
        }
    }

    private static bool Writes(string formatter, string member) => formatter.Contains("value." + member);

    [Fact]
    public async Task Generator_DuplicateIntKeys_DoesNotThrow()
    {
        var (error, _) = await this.RunGeneratorAsync(DuplicateIntKeys, "dup-int");
        AssertNoCrash(error);
    }

    [Fact]
    public async Task Generator_DuplicateIntKeys_SerializesFirstMemberOnly()
    {
        var (error, formatter) = await this.RunGeneratorAsync(DuplicateIntKeys, "dup-int");
        AssertNoCrash(error);
        Assert.NotNull(formatter);
        Assert.True(Writes(formatter!, "First"), "First should be serialized");
        Assert.False(Writes(formatter!, "Second"), "Second should be dropped");
    }

    [Fact]
    public async Task Generator_DuplicateStringKeys_SerializesFirstMemberOnly()
    {
        var (error, formatter) = await this.RunGeneratorAsync(DuplicateStringKeys, "dup-string");
        AssertNoCrash(error);
        Assert.NotNull(formatter);
        Assert.True(Writes(formatter!, "First"));
        Assert.False(Writes(formatter!, "Second"));
    }

    [Fact]
    public async Task Generator_MixedKeys_SkipsMismatchedMember()
    {
        var (error, formatter) = await this.RunGeneratorAsync(MixedKeys, "mixed");
        AssertNoCrash(error);
        Assert.NotNull(formatter);
        Assert.True(Writes(formatter!, "First"));
        Assert.False(Writes(formatter!, "Second"));
    }
}
