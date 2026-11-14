// Earned Trust — drill evidence for ju26-issue-2234 (B3, two-sided calibration).
// NOT part of the normal receipts (lives in drills/, so verify scripts don't inject it; the ledger is unchanged).
// Run by `uv run et drill 2234` on the PR head and on the head with mutant M04 planted, so the drill's
// reveal shows executed generator output, not a description of the mutant.
#nullable enable

using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.Testing;

namespace MessagePack.SourceGenerator.Tests;

public class EtDrillTests
{
    private readonly ITestOutputHelper logger;

    public EtDrillTests(ITestOutputHelper logger) => this.logger = logger;

    // A string-keyed member in the MIDDLE of int-keyed members: the mismatched member is skipped,
    // and the question is whether the members after it survive.
    private const string MixedKeyInTheMiddle = """
        using MessagePack;
        [MessagePackObject]
        public class Foo
        {
            [Key(0)] public int First { get; set; }
            [Key("b")] public int Second { get; set; }
            [Key(1)] public int Third { get; set; }
        }
        """;

    [Fact]
    public async Task Drill_MixedKeyInTheMiddle_LaterMembersStillSerialized()
    {
        var refs = await ReferenceAssemblies.Net.Net80.ResolveAsync(LanguageNames.CSharp, CancellationToken.None);
        var parse = new CSharpParseOptions(LanguageVersion.Latest);
        var compilation = CSharpCompilation.Create(
            "EtDrill",
            new[] { CSharpSyntaxTree.ParseText(MixedKeyInTheMiddle, parse) },
            refs.AddRange(ReferencesHelper.GetReferences(ReferencesSet.MessagePack)),
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        GeneratorDriver driver = CSharpGeneratorDriver.Create(new[] { new MessagePackGenerator().AsSourceGenerator() }, parseOptions: parse);
        var result = driver.RunGenerators(compilation).GetRunResult().Results.Single();
        string? formatter = result.GeneratedSources.Where(s => s.HintName.Contains("FooFormatter")).Select(s => s.SourceText.ToString()).FirstOrDefault();
        string report = result.Exception is not null
            ? $"GENERATOR THREW: {result.Exception.GetType().Name}: {result.Exception.Message}"
            : formatter ?? "(no formatter generated for Foo)";
        this.logger.WriteLine(report);
        string? dir = System.Environment.GetEnvironmentVariable("ET_EVIDENCE_DIR");
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, "drill-mixed-middle.txt"), report);
        }

        Assert.Null(result.Exception);
        Assert.NotNull(formatter);
        Assert.Contains("value.First", formatter);
        Assert.DoesNotContain("value.Second", formatter);
        Assert.Contains("value.Third", formatter);
    }
}
