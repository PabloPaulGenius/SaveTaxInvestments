import InvestmentCalculator from "@/components/investment-calculator" // Import the calculator UI
import { createClient } from '@/app/utils/supabase/server' // Import Supabase client creator

// This is the main page component for your app
export default async function Page() {
  // Create a Supabase client for this request
  const supabase = await createClient()
  // Fetch all todos from the 'todos' table (if you have one)
  const { data: todos } = await supabase.from('todos').select()

  // Render the page
  return (
    <main className="container mx-auto py-10 px-4">
      {/* Show the investment calculator */}
      <InvestmentCalculator />
      {/* Show a list of todos (if any) */}
      <ul>
        {todos?.map((todo) => (
          // Each todo should have an id and a task property
          <li key={todo.id}>{todo.task}</li>
        ))}
      </ul>
    </main>
  )
}