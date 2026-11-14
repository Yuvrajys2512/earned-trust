// Earned Trust — catching tests written by the REVIEWER (not the author agent) for ju26-issue-2297.
// Copied into tests/MessagePack.SourceGenerator.Tests/ of both the BASE and HEAD worktrees.
//   fails on BASE, passes on HEAD  -> catching: proven behavior change
//   passes on BASE, fails on HEAD  -> broken-by-pr: proven regression
//   passes on both                 -> placebo for this PR (used here as a fact check of the agent's story)
// Unlike the agent's CodeCoverageExclusionTests (string search in generated text), these ask the
// compiler: which types actually carry the attribute, and does the consumer's code still compile?
#nullable enable

using System.Collections.Immutable;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.Testing;

namespace MessagePack.SourceGenerator.Tests;

public class EtCoverageReceiptsTests
{
    private const string AttrName = "System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverageAttribute";

    private readonly ITestOutputHelper logger;

    public EtCoverageReceiptsTests(ITestOutputHelper logger) => this.logger = logger;

    private const string Model = """
        using MessagePack;
        [MessagePackObject]
        public class Foo { [Key(0)] public int Value { get; set; } }
        """;

    private const string PlainResolver = """
        namespace App { [MessagePack.GeneratedMessagePackResolver] partial class MyResolver { } }
        """;

    // A user who already excluded their own resolver from coverage (a reasonable thing to have done before #2297).
    private const string UserExcludedResolver = """
        namespace App
        {
            [MessagePack.GeneratedMessagePackResolver]
            [System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
            partial class MyResolver { }
        }
        """;

    private async Task<(CSharpCompilation Output, ImmutableArray<Diagnostic> Errors)> GenerateAndCompileAsync(
        ReferenceAssemblies frameworkRefs, string[] preprocessorSymbols, string evidenceName, params string[] sources)
    {
        var refs = await frameworkRefs.ResolveAsync(LanguageNames.CSharp, CancellationToken.None);
        var parse = new CSharpParseOptions(LanguageVersion.Latest, preprocessorSymbols: preprocessorSymbols);
        var compilation = CSharpCompilation.Create(
            "EtCoverage",
            sources.Select(s => CSharpSyntaxTree.ParseText(s, parse)),
            refs.AddRange(ReferencesHelper.GetReferences(ReferencesSet.MessagePack)),
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));

        GeneratorDriver driver = CSharpGeneratorDriver.Create(
            new[] { new MessagePackGenerator().AsSourceGenerator() }, parseOptions: parse);
        driver.RunGeneratorsAndUpdateCompilation(compilation, out Compilation output, out _);
        var errors = output.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error).ToImmutableArray();

        string report = string.Join("\n", errors.Select(e => e.ToString()));
        string resolverSource = string.Join("\n// ----\n", output.SyntaxTrees.Skip(sources.Length)
            .Where(t => t.FilePath.Contains("MyResolver"))
            .Select(t => t.ToString()));
        this.logger.WriteLine(report);
        string? dir = System.Environment.GetEnvironmentVariable("ET_EVIDENCE_DIR");
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
            File.WriteAllText(
                Path.Combine(dir, evidenceName + ".txt"),
                $"errors: {errors.Length}\n{report}\n\n// generated resolver source\n{resolverSource}");
        }

        return ((CSharpCompilation)output, errors);
    }

    private static bool Excluded(Compilation c, string metadataName)
    {
        INamedTypeSymbol? type = c.GetTypeByMetadataName(metadataName);
        Assert.NotNull(type);
        return type!.GetAttributes().Any(a => a.AttributeClass?.ToDisplayString() == AttrName);
    }

    /// <summary>The intended change, checked semantically: on net8.0 the generated resolver type carries the attribute.</summary>
    [Fact]
    public async Task Net80_GeneratedResolver_IsExcludedFromCoverage()
    {
        var (output, _) = await this.GenerateAndCompileAsync(ReferenceAssemblies.Net.Net80, new[] { "NET8_0", "NETCOREAPP" }, "net80-resolver", Model, PlainResolver);
        Assert.True(Excluded(output, "App.MyResolver"), "App.MyResolver has no [ExcludeFromCodeCoverage]");
    }

    /// <summary>
    /// The requirement asks generated code to be excluded from coverage. A consumer compiling for netstandard2.0
    /// (e.g. a Unity or shared library) gets the attribute only if the guard lets it through.
    /// </summary>
    [Fact]
    public async Task NetStandard20_GeneratedResolver_IsExcludedFromCoverage()
    {
        var (output, _) = await this.GenerateAndCompileAsync(ReferenceAssemblies.NetStandard.NetStandard20, new[] { "NETSTANDARD2_0", "NETSTANDARD" }, "ns20-resolver", Model, PlainResolver);
        Assert.True(Excluded(output, "App.MyResolver"), "App.MyResolver has no [ExcludeFromCodeCoverage] when the consumer targets netstandard2.0");
    }

    /// <summary>
    /// A consumer that had already put [ExcludeFromCodeCoverage] on its own partial resolver.
    /// The attribute is AllowMultiple = false, so a second copy from the generator would be CS0579.
    /// </summary>
    [Fact]
    public async Task UserExcludedResolver_StillCompiles()
    {
        var (_, errors) = await this.GenerateAndCompileAsync(ReferenceAssemblies.Net.Net80, new[] { "NET8_0", "NETCOREAPP" }, "user-excluded-resolver", Model, UserExcludedResolver);
        Assert.True(errors.IsEmpty, "consumer build breaks:\n" + string.Join("\n", errors));
    }

    /// <summary>
    /// Fact check of the agent's story ("the attribute is not available on netstandard2.0 or .NET Framework").
    /// Passes on both sides by design: it tests the platform, not the PR.
    /// </summary>
    [Fact]
    public async Task Story_AttributeIsAvailableOnNetStandard20AndNetFramework()
    {
        const string probe = """
            [System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
            partial class C { [System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage] private static class N { } }
            """;
        foreach (var (name, fw) in new[] { ("netstandard2.0", ReferenceAssemblies.NetStandard.NetStandard20), ("net472", ReferenceAssemblies.NetFramework.Net472.Default) })
        {
            var refs = await fw.ResolveAsync(LanguageNames.CSharp, CancellationToken.None);
            var c = CSharpCompilation.Create("Probe", new[] { CSharpSyntaxTree.ParseText(probe) }, refs, new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
            var errors = c.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error).ToList();
            this.logger.WriteLine($"{name}: {errors.Count} errors {string.Join("; ", errors)}");
            Assert.True(errors.Count == 0, $"{name}: " + string.Join("; ", errors));
        }
    }
}
