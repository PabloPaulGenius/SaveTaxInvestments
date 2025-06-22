"use client" // This tells Next.js this component runs on the client (browser)

import { useState } from "react"
import { z } from "zod" // For schema validation
import { useForm } from "react-hook-form" // For form state management
import { zodResolver } from "@hookform/resolvers/zod" // To use zod with react-hook-form
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

// Define the form schema using zod
const formSchema = z.object({
  freibetrag: z.string().min(1, { message: "Freibetrag ist erforderlich" }),
  choice: z.string().optional(),
  dividendenrendite: z.string().optional(),
  isin: z.string().min(1, { message: "ISIN ist erforderlich" }),
})

type FormValues = z.infer<typeof formSchema> // Type for form values

export default function InvestmentCalculator() {
  // State variables for UI and calculation
  const [calculating, setCalculating] = useState(false)
  const [result, setResult] = useState<number | null>(null)
  const [isinInfo, setIsinInfo] = useState<string | null>(null)
  const [etfFacts, setEtfFacts] = useState<any | null>(null) // All ETF facts from API
  const [divRenditeHint, setDivRenditeHint] = useState<string | null>(null) // Hint about DivRendite
  const [error, setError] = useState<string | null>(null)

  // Set up the form with react-hook-form and zod validation
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      freibetrag: "1000",
      choice: "",
      dividendenrendite: "",
      isin: "",
    },
  })

  // This function runs when the form is submitted
  const onSubmit = async (data: FormValues) => {
    setCalculating(true)
    setError(null)
    setEtfFacts(null)
    setDivRenditeHint(null)

    try {
      // Parse the freibetrag (allowing decimals)
      const freibetrag = Number.parseFloat(data.freibetrag)
      let dividendenrendite: number | null = null
      let facts = null

      if (data.choice === "option1") {
        // Fetch all ETF facts from the API using the ISIN
        const response = await fetch(`/api/etf?isin=${data.isin}`)
        if (!response.ok) {
          const errorData = await response.json()
          if (response.status === 404) {
            setDivRenditeHint("Dividendenrendite konnte nicht gefunden werden.")
            throw new Error(`ETF mit ISIN ${data.isin} wurde nicht gefunden. Bitte überprüfen Sie die ISIN.`)
          }
          throw new Error(errorData.error || 'Fehler beim Abrufen der ETF-Daten')
        }
        facts = await response.json()
        setEtfFacts(facts) // Save all ETF facts for display
        if (facts.dividendenrendite && facts.dividendenrendite !== "no DivRendite found") {
          setDivRenditeHint(`Dividendenrendite wurde aus der Datenbank übernommen. Im Jahr 2024 betrug sie: ${facts.dividendenrendite} \nVorraussichtlich wird sie dieses Jahr ähnlich groß sein.`)
          dividendenrendite = Number.parseFloat(facts.dividendenrendite.replace("%", "")) / 100
        } else {
          setDivRenditeHint("Dividendenrendite konnte nicht gefunden werden, möglicherweise ist für diesen ETF keine Dividendenrendite verfügbar.")
          throw new Error("Dividendenrendite wurde nicht gefunden.")
        }
      } else {
        // Use manually entered Dividendenrendite
        dividendenrendite = Number.parseFloat(data.dividendenrendite!.replace("%", "")) / 100
      }

      // Calculate the max investment volume
      const maxInvestmentVolume = (freibetrag / 0.7) / (dividendenrendite ?? 1)
      setResult(maxInvestmentVolume)
      setIsinInfo(`Information for ISIN: ${data.isin}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ein Fehler ist aufgetreten')
    } finally {
      setCalculating(false)
    }
  }

  //------------------------------------------
  // Render the calculator UI
  return (
    <Card className="max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="text-3xl font-bold">Investment Rechner</CardTitle>
        <CardDescription>Steuereffizient in ETFs investieren</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            {/* Freibetrag input */}
            <FormField
              control={form.control}
              name="freibetrag"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-base font-medium">
                    Freibetrag<span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Choice select */}
            <div className="space-y-2">
              <Label htmlFor="choice" className="text-base font-medium">
                Select a Choice
              </Label>
              <Select onValueChange={(value) => form.setValue("choice", value)}>
                <SelectTrigger>
                  <SelectValue placeholder="please select ..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="option1">Optimales Investmentvolumen für ausschüttende ETFs herausfinden</SelectItem>
                  <SelectItem value="option2">Option 2 (noch nicht verfügbar)</SelectItem>
                  <SelectItem value="option3">Option 3 (noch nicht verfügbar)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Dividendenrendite input (only for non-option1) */}
            {form.watch("choice") !== "option1" && (
              <FormField
                control={form.control}
                name="dividendenrendite"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-base font-medium">
                      Dividendenrendite
                      <span className="text-red-500">*</span>
                      <p className="text-sm font-normal text-muted-foreground mt-1">
                        (Das Verhältnis der über die letzten 12 Monate ausgeschütteten Erträge zum aktuellen
                        Nettoinventarwert des Fonds)
                      </p>
                    </FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {/* ISIN input */}
            <FormField
              control={form.control}
              name="isin"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-base font-medium">
                    ISIN<span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Submit button and info */}
            <div>
              <Button type="submit" className="w-40 bg-blue-600 hover:bg-blue-700" disabled={calculating}>
                Berechnen
              </Button>
              <p className="text-sm text-muted-foreground mt-1">
                Basierend auf der Dividendenrendite Deines ETFs und Deinem Freibetrag wird das optimale Investmentvolumen berechnet,
                bis zu dem Du in ausschüttende ETFs investieren solltest. Darüber hinaus empfehlen sich aus steuerlicher Sicht eher thesaurierende ETFs.
              </p>
            </div>

            {/* Error message */}
            {error && (
              <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">
                {error}
              </div>
            )}

            {/* Show the Dividendenrendite hint - display regardless of result/error */}
            {divRenditeHint && (
              <div className="mt-4 p-4 text-sm text-blue-700 bg-blue-50 rounded-md">
                {divRenditeHint}
              </div>
            )}

            {/* Loading indicator */}
            {calculating && (
              <div className="mt-6">
                <h3 className="text-xl font-semibold mb-4">Calculating ...</h3>
              </div>
            )}

            {/* Results */}
            {result !== null && !calculating && (
              <div className="space-y-6 mt-4">
                <h3 className="text-xl font-semibold">Ergebnis</h3>

                {/* Show the calculated max investment volume */}
                <div className="space-y-2">
                  <Label htmlFor="result" className="text-base font-medium">
                    max. Investment Volumen
                  </Label>
                  <Input id="result" value={result.toFixed(2)} readOnly />
                </div>

                {/* Show all ETF facts in a table */}
                {etfFacts && etfFacts.dividendenrendite && etfFacts.dividendenrendite !== "no DivRendite found" && (
                  <div className="mt-6">
                    <h3 className="text-lg font-medium mb-2">ETF Details</h3>
                    <table className="min-w-full border text-sm">
                      <tbody>
                        {Object.entries(etfFacts).map(([key, value]) => (
                          <tr key={key}>
                            <td className="border px-2 py-1 font-semibold capitalize">{key}</td>
                            <td className="border px-2 py-1">{String(value)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Footer and ISIN info */}
            <div className="mt-6">
              <p className="text-sm font-medium mb-2">Herausgeber: Paul Faschingbauer <br />
                Für Schäden, die durch die Nutzung dieser Informationen entstehen, wird keine Haftung übernommen</p>
              {isinInfo && <p>{isinInfo}</p>}
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}